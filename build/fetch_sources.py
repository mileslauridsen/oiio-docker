#!/usr/bin/env python3
"""Fetch locked source archives and wheels, verifying each before extraction."""

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

CHUNK_SIZE = 1024 * 1024
PLATFORMS = ("linux/amd64", "linux/arm64")


def load_lock(path):
    with open(path, "r") as lock_file:
        lock = json.load(lock_file)
    if lock.get("lock_version") != 1:
        raise ValueError("unsupported lock_version: {0}".format(lock.get("lock_version")))
    dependencies = lock.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise ValueError("lockfile must contain a non-empty dependencies list")
    seen = set()
    archives = set()
    for dependency in dependencies:
        name = dependency.get("name")
        kind = dependency.get("kind", "source")
        platform = dependency.get("platform")
        if not name:
            raise ValueError("dependency names must be present")
        if kind not in ("source", "wheel"):
            raise ValueError("{0}: unknown kind {1}".format(name, kind))
        if kind == "wheel" and platform not in PLATFORMS:
            raise ValueError("{0}: wheels must name a platform in {1}".format(name, PLATFORMS))
        key = (name, platform)
        if key in seen:
            raise ValueError("{0}: duplicate dependency for platform {1}".format(name, platform))
        seen.add(key)
        if not re.match(r"^[0-9a-fA-F]{64}$", dependency.get("sha256", "")):
            raise ValueError("{0}: sha256 must contain 64 hexadecimal characters".format(name))
        archive = dependency.get("archive", "")
        if not archive or os.path.basename(archive) != archive or archive in archives:
            raise ValueError("{0}: archive must be a unique filename".format(name))
        archives.add(archive)
        if not dependency.get("url", "").startswith("https://"):
            raise ValueError("{0}: source URL must use HTTPS".format(name))
        if kind == "source" and not dependency.get("source_root"):
            raise ValueError("{0}: source_root is required".format(name))
    return dependencies


def download(url, destination):
    temporary = destination + ".part"
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "oiio-docker-locked-source-fetcher/1"})
            response = urlopen(request, timeout=120)
            try:
                if not response.geturl().startswith("https://"):
                    raise ValueError("download redirected away from HTTPS: {0}".format(response.geturl()))
                with open(temporary, "wb") as output:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        output.write(chunk)
            finally:
                response.close()
            os.rename(temporary, destination)
            return
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(dependency, archive_path):
    actual = sha256_file(archive_path)
    expected = dependency["sha256"].lower()
    if actual.lower() != expected:
        raise ValueError(
            "{0}: SHA-256 mismatch for {1}: expected {2}, got {3}".format(
                dependency["name"], archive_path, expected, actual
            )
        )
    print("{0}: SHA-256 verified ({1})".format(dependency["name"], actual))


def extract_source(dependency, archive_path, extract_dir):
    if not os.path.isdir(extract_dir):
        os.makedirs(extract_dir)
    target = os.path.join(extract_dir, dependency["name"])
    if os.path.exists(target):
        shutil.rmtree(target)
    temporary = tempfile.mkdtemp(prefix="source-extract-", dir=extract_dir)
    try:
        subprocess.check_call(["tar", "-xf", archive_path, "-C", temporary])
        source_root = dependency["source_root"]
        normalized = posixpath.normpath(source_root)
        if normalized.startswith("../") or normalized.startswith("/") or normalized != source_root:
            raise ValueError("{0}: invalid source_root".format(dependency["name"]))
        extracted = os.path.join(temporary, source_root)
        if not os.path.isdir(extracted):
            raise ValueError("{0}: archive did not contain expected root {1}".format(dependency["name"], source_root))
        shutil.move(extracted, target)
        print("{0}: extracted verified source to {1}".format(dependency["name"], target))
    finally:
        shutil.rmtree(temporary)


def selected_dependencies(dependencies, platform, name=None):
    selected = []
    for dependency in dependencies:
        if dependency.get("kind", "source") == "wheel" and dependency["platform"] != platform:
            continue
        if name is not None and dependency["name"] != name:
            continue
        selected.append(dependency)
    if name is not None and not selected:
        raise ValueError("unknown dependency for {0}: {1}".format(platform, name))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lockfile", required=True)
    parser.add_argument("--platform", required=True, choices=PLATFORMS, help="select wheels for this platform")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--all", action="store_true", help="fetch and verify every locked input for the platform")
    modes.add_argument("--name", help="fetch and verify one named input")
    modes.add_argument("--verify-archive", metavar="NAME", help="verify a local archive without downloading it")
    parser.add_argument("--archive", help="archive path for --verify-archive")
    parser.add_argument("--output-dir", default="/src/downloads")
    parser.add_argument("--extract-dir", help="also extract each verified source archive into a directory named for it")
    args = parser.parse_args()

    try:
        dependencies = load_lock(args.lockfile)
        if args.verify_archive:
            if not args.archive:
                parser.error("--verify-archive requires --archive")
            dependency = selected_dependencies(dependencies, args.platform, args.verify_archive)[0]
            verify_archive(dependency, args.archive)
            if args.extract_dir and dependency.get("kind", "source") == "source":
                extract_source(dependency, args.archive, args.extract_dir)
            return 0

        if not os.path.isdir(args.output_dir):
            os.makedirs(args.output_dir)
        for dependency in selected_dependencies(dependencies, args.platform, args.name):
            archive_path = os.path.join(args.output_dir, dependency["archive"])
            if not os.path.isfile(archive_path):
                print("Fetching {0} {1}".format(dependency["name"], dependency["version"]))
                download(dependency["url"], archive_path)
            verify_archive(dependency, archive_path)
            if args.extract_dir and dependency.get("kind", "source") == "source":
                extract_source(dependency, archive_path, args.extract_dir)
        return 0
    except Exception as error:
        print("source lock error: {0}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
