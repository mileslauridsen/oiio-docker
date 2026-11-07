#!/usr/bin/env python3
"""Resolve a year's builder RPM closure from its pinned Rocky repositories and write the package manifests."""

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLATFORMS = ("linux/amd64", "linux/arm64")
QUERY_FORMAT = "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n"
MARKER = "=== installed after resolution ==="


def image_reference(image):
    return "%s@%s" % (image["reference"], image["index_digest"])


def installed(platform, image, script, mounts=()):
    command = ["docker", "run", "--rm", "--platform", platform]
    for source, target in mounts:
        command += ["-v", "%s:%s:ro" % (source, target)]
    command += [image, "sh", "-c", script]
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, universal_newlines=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, choices=("cy2025", "cy2026", "cy2027"))
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    args = parser.parse_args()

    lock = json.loads((ROOT / "build" / "locks" / (args.year + ".json")).read_text(encoding="utf-8"))
    toolchain = lock["toolchain"]
    requested = toolchain["rpm"]["requested"]
    rpm_dir = ROOT / "build" / "rpm" / args.year
    architecture = args.platform.split("/")[1]

    # dnf output goes to stderr so stdout holds only the two sorted package lists.
    query = "rpm -qa --qf '%s' | sort" % QUERY_FORMAT
    script = "set -eu; %s; echo '%s'; dnf -y --setopt=reposdir=/rpm install %s >&2; %s" % (
        query, MARKER, " ".join(requested), query)
    before, after = installed(args.platform, image_reference(toolchain["builder_image"]), script,
                              [(str(rpm_dir), "/rpm")]).split(MARKER + "\n")
    before, after = sorted(before.splitlines()), sorted(after.splitlines())
    runtime = sorted(installed(args.platform, image_reference(toolchain["runtime_image"]), query).splitlines())

    # Install every added or changed package by exact NEVRA, so dnf has nothing left to choose.
    # gpg-pubkey is the repository key dnf imports, not an installable package.
    builder = sorted(package for package in set(after) - set(before) if not package.startswith("gpg-pubkey-"))
    # A requested package the base image already has at the resolved version is not reinstalled.
    missing = [name for name in requested if not any(package.startswith(name + "-") for package in after)]
    if missing:
        raise SystemExit("requested packages are absent from the resolved closure: %s" % missing)
    for name, packages in (("builder", builder), ("resolved", after), ("runtime", runtime)):
        path = rpm_dir / ("%s-%s.packages" % (name, architecture))
        path.write_text("\n".join(packages) + "\n", encoding="utf-8")
        print("%s: %d packages" % (path.relative_to(ROOT), len(packages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
