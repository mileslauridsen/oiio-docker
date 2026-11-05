#!/usr/bin/env python3
"""Fetch locked sources, wheels, and tools, verifying checksums and signatures before extraction."""

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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNK_SIZE = 1024 * 1024
PLATFORMS = ("linux/amd64", "linux/arm64")
KINDS = ("source", "wheel", "tool")
PLATFORM_KINDS = ("wheel", "tool")
SIGSTORE_ISSUER = "https://token.actions.githubusercontent.com"


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
        if kind not in KINDS:
            raise ValueError("{0}: unknown kind {1}".format(name, kind))
        if kind in PLATFORM_KINDS and platform not in PLATFORMS:
            raise ValueError("{0}: {1} entries must name a platform in {2}".format(name, kind, PLATFORMS))
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
        for signature in dependency.get("signatures", []):
            check_signature_entry(name, signature)
    return dependencies


def check_signature_entry(name, signature):
    kind = signature.get("type")
    if not signature.get("url", "").startswith("https://"):
        raise ValueError("{0}: signature URL must use HTTPS".format(name))
    signature_file = signature.get("file", "")
    if not signature_file or os.path.basename(signature_file) != signature_file:
        raise ValueError("{0}: signature file must be a filename".format(name))
    if kind == "gpg":
        if not re.match(r"^[0-9A-F]{40}$", signature.get("fingerprint", "")):
            raise ValueError("{0}: GPG fingerprint must be 40 uppercase hexadecimal characters".format(name))
        if not signature.get("key_file"):
            raise ValueError("{0}: GPG signatures need a pinned key_file".format(name))
    elif kind == "sigstore":
        if not signature.get("certificate_identity", "").startswith("https://github.com/"):
            raise ValueError("{0}: Sigstore signatures need an exact GitHub workflow identity".format(name))
        if signature.get("certificate_oidc_issuer") != SIGSTORE_ISSUER:
            raise ValueError("{0}: Sigstore issuer must be {1}".format(name, SIGSTORE_ISSUER))
        if not signature.get("trusted_root"):
            raise ValueError("{0}: Sigstore signatures need a pinned trusted_root".format(name))
        if not re.match(r"^[0-9a-f]{64}$", signature.get("trusted_root_sha256", "")):
            raise ValueError("{0}: trusted_root_sha256 must be 64 lowercase hexadecimal characters".format(name))
    else:
        raise ValueError("{0}: unknown signature type {1}".format(name, kind))


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


def verify_gpg(dependency, signature, archive_path, signature_path, work_dir):
    key_path = os.path.join(SCRIPT_DIR, signature["key_file"])
    if not os.path.isfile(key_path):
        raise ValueError("pinned signing key is missing: {0}".format(key_path))
    gpg = shutil.which("gpg2") or shutil.which("gpg")
    gpgv = shutil.which("gpgv2") or shutil.which("gpgv")
    if not gpg or not gpgv:
        raise ValueError("GPG signature verification requires gpg and gpgv")
    keyring = os.path.join(tempfile.mkdtemp(prefix="gpg-", dir=work_dir), "trustedkeys.gpg")
    with open(key_path, "rb") as key_input, open(keyring, "wb") as keyring_output:
        subprocess.check_call([gpg, "--no-options", "--batch", "--dearmor"], stdin=key_input, stdout=keyring_output)
    process = subprocess.run([gpgv, "--status-fd=1", "--keyring", keyring, signature_path, archive_path],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if process.returncode != 0:
        raise ValueError("{0}: detached signature verification failed\n{1}".format(dependency["name"], process.stdout))
    # VALIDSIG lists the signing (sub)key fingerprint and, last, the primary key fingerprint.
    valid = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) > 2 and fields[0] == "[GNUPG:]" and fields[1] == "VALIDSIG":
            valid.extend(value.upper() for value in fields[2:] if len(value) == 40)
    if signature["fingerprint"] not in valid:
        raise ValueError("{0}: signature is valid but not from pinned fingerprint {1}\n{2}".format(
            dependency["name"], signature["fingerprint"], process.stdout))
    print("{0}: GPG signature verified with {1}".format(dependency["name"], signature["fingerprint"]))


def verify_sigstore(dependency, signature, archive_path, bundle_path, cosign, work_dir):
    # The pinned trust root replaces cosign's online TUF fetch, so verification needs no network.
    trusted_root = os.path.join(SCRIPT_DIR, signature["trusted_root"])
    actual = sha256_file(trusted_root)
    if actual != signature["trusted_root_sha256"]:
        raise ValueError("{0}: Sigstore trusted root SHA-256 mismatch: expected {1}, got {2}".format(
            dependency["name"], signature["trusted_root_sha256"], actual))
    if not cosign:
        raise ValueError("{0}: Sigstore verification requires the locked cosign tool".format(dependency["name"]))
    # Keep anything cosign writes under $HOME out of the source tree.
    environment = dict(os.environ, HOME=work_dir)
    process = subprocess.run(
        [cosign, "verify-blob", "--trusted-root", trusted_root, "--bundle", bundle_path,
         "--certificate-identity", signature["certificate_identity"],
         "--certificate-oidc-issuer", signature["certificate_oidc_issuer"], archive_path],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=environment)
    if process.returncode != 0:
        raise ValueError("{0}: Sigstore verification failed\n{1}".format(dependency["name"], process.stdout))
    print("{0}: Sigstore signature verified for {1}".format(dependency["name"], signature["certificate_identity"]))


def verify_signatures(dependency, archive_path, signature_dir, cosign, work_dir, fetch):
    for signature in dependency.get("signatures", []):
        signature_path = os.path.join(signature_dir, signature["file"])
        if fetch and not os.path.isfile(signature_path):
            download(signature["url"], signature_path)
        if not os.path.isfile(signature_path):
            raise ValueError("{0}: signature file is missing: {1}".format(dependency["name"], signature_path))
        if signature["type"] == "gpg":
            verify_gpg(dependency, signature, archive_path, signature_path, work_dir)
        else:
            verify_sigstore(dependency, signature, archive_path, signature_path, cosign, work_dir)


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
        if dependency.get("kind", "source") in PLATFORM_KINDS and dependency["platform"] != platform:
            continue
        # A named fetch still takes the platform's tools, which may be needed to verify it.
        if name is not None and dependency["name"] != name and dependency.get("kind", "source") != "tool":
            continue
        selected.append(dependency)
    if name is not None and not any(dependency["name"] == name for dependency in selected):
        raise ValueError("unknown dependency for {0}: {1}".format(platform, name))
    # Tools first, so cosign is verified before it checks any Sigstore bundle.
    return sorted(selected, key=lambda dependency: dependency.get("kind", "source") != "tool")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lockfile", required=True)
    parser.add_argument("--platform", required=True, choices=PLATFORMS, help="select wheels and tools for this platform")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--all", action="store_true", help="fetch and verify every locked input for the platform")
    modes.add_argument("--name", help="fetch and verify one named input")
    modes.add_argument("--verify-archive", metavar="NAME", help="verify a local archive without downloading it")
    parser.add_argument("--archive", help="archive path for --verify-archive")
    parser.add_argument("--signature-dir", help="directory holding local signatures for --verify-archive")
    parser.add_argument("--cosign", help="cosign executable for --verify-archive Sigstore checks")
    parser.add_argument("--output-dir", default="/src/downloads")
    parser.add_argument("--extract-dir", help="also extract each verified source archive into a directory named for it")
    args = parser.parse_args()

    work_dir = tempfile.mkdtemp(prefix="fetch-sources-")
    try:
        dependencies = load_lock(args.lockfile)
        if args.verify_archive:
            if not args.archive:
                parser.error("--verify-archive requires --archive")
            dependency = next(item for item in selected_dependencies(dependencies, args.platform, args.verify_archive)
                              if item["name"] == args.verify_archive)
            verify_archive(dependency, args.archive)
            verify_signatures(dependency, args.archive, args.signature_dir or os.path.dirname(args.archive),
                              args.cosign, work_dir, fetch=False)
            if args.extract_dir and dependency.get("kind", "source") == "source":
                extract_source(dependency, args.archive, args.extract_dir)
            return 0

        if not os.path.isdir(args.output_dir):
            os.makedirs(args.output_dir)
        cosign = None
        for dependency in selected_dependencies(dependencies, args.platform, args.name):
            archive_path = os.path.join(args.output_dir, dependency["archive"])
            if not os.path.isfile(archive_path):
                print("Fetching {0} {1}".format(dependency["name"], dependency["version"]))
                download(dependency["url"], archive_path)
            verify_archive(dependency, archive_path)
            verify_signatures(dependency, archive_path, args.output_dir, cosign, work_dir, fetch=True)
            kind = dependency.get("kind", "source")
            if kind == "tool":
                os.chmod(archive_path, 0o755)
                if dependency["name"] == "cosign":
                    cosign = archive_path
            elif args.extract_dir and kind == "source":
                extract_source(dependency, archive_path, args.extract_dir)
        return 0
    except Exception as error:
        print("source lock error: {0}".format(error), file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
