#!/usr/bin/env python3
"""Copy the license and notice files of every shipped locked component, and write a manifest of them."""

import argparse
import hashlib
import json
import os
import shutil
import sys

NOTICE_PREFIXES = ("COPYING", "LICENSE", "LICENCE", "COPYRIGHT", "NOTICE", "PATENTS", "THIRD-PARTY", "THIRD_PARTY")
# Bundled code keeps its notices in subdirectories, such as OpenEXR's external/ and CPython's Modules/.
# Tests, examples, contributed extras, other platforms' packaging, and documentation copies are not built.
MAX_DEPTH = 3
SKIP_DIRECTORIES = {".git", ".github", "test", "tests", "testsuite", "testdata", "testing", "example", "examples",
                    "benchmark", "benchmarks", "contrib", "ci", "java", "mac", "release", "doc", "docs", "website"}
# Notices outside the usual names: the IJG terms libjpeg-turbo must reproduce, and CPython's list of the
# third-party code it incorporates.
EXTRA_FILES = {"libjpeg-turbo": ["README.ijg"], "cpython": ["Doc/license.rst"]}
PLATFORM_KINDS = ("wheel", "tool")


def is_notice(filename):
    return filename.upper().startswith(NOTICE_PREFIXES)


def source_notices(root, name):
    found = []
    for current, directories, filenames in os.walk(root):
        relative = os.path.relpath(current, root)
        depth = 0 if relative == "." else len(relative.split(os.sep))
        directories[:] = sorted(d for d in directories if d.lower() not in SKIP_DIRECTORIES and depth < MAX_DEPTH)
        found.extend(os.path.normpath(os.path.join(relative, f)) for f in filenames if is_notice(f))
    for extra in EXTRA_FILES.get(name, []):
        if not os.path.isfile(os.path.join(root, extra)):
            raise RuntimeError("{0}: expected notice file {1} is missing".format(name, extra))
        found.append(extra)
    return sorted(set(found))


def wheel_notices(site_packages, name, version):
    dist_info = "{0}-{1}.dist-info".format(name, version)
    root = os.path.join(site_packages, dist_info)
    found = []
    for current, _directories, filenames in os.walk(root):
        relative = os.path.relpath(current, root)
        in_licenses = relative.split(os.sep)[0] == "licenses"
        found.extend(os.path.normpath(os.path.join(relative, f)) for f in filenames if in_licenses or is_notice(f))
    return root, sorted(found)


def collect(lock, platform, source_dir, site_packages, output_dir):
    components = []
    for dependency in lock["dependencies"]:
        kind = dependency.get("kind", "source")
        if kind in PLATFORM_KINDS and dependency["platform"] != platform:
            continue
        if not dependency["shipped"]:
            continue
        name, version = dependency["name"], dependency["version"]
        if kind == "source":
            root = os.path.join(source_dir, name)
            files = source_notices(root, name)
        elif kind == "wheel":
            root, files = wheel_notices(site_packages, name, version)
        else:
            raise RuntimeError("{0}: a {1} cannot be shipped".format(name, kind))
        if not files:
            raise RuntimeError("{0}: no license or notice files found in {1}".format(name, root))
        entries = []
        for relative in files:
            destination = os.path.join(output_dir, name, relative)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(os.path.join(root, relative), destination)
            with open(destination, "rb") as handle:
                entries.append({"path": os.path.join(name, relative), "sha256": hashlib.sha256(handle.read()).hexdigest()})
        components.append({"name": name, "version": version, "files": entries})
        print("{0} {1}: {2} notice files".format(name, version, len(entries)))
    manifest = {"schema_version": 1, "platform_year": lock["platform_year"], "platform": platform,
                "components": sorted(components, key=lambda item: item["name"])}
    with open(os.path.join(output_dir, "components.json"), "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lockfile", required=True)
    parser.add_argument("--platform", required=True, choices=("linux/amd64", "linux/arm64"))
    parser.add_argument("--source-dir", required=True, help="directory holding each extracted source by name")
    parser.add_argument("--site-packages", required=True, help="directory where the locked wheels are installed")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    with open(args.lockfile) as handle:
        lock = json.load(handle)
    os.makedirs(args.output_dir)
    collect(lock, args.platform, args.source_dir, args.site_packages, args.output_dir)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, KeyError) as error:
        print("license collection error: {0}".format(error), file=sys.stderr)
        sys.exit(1)
