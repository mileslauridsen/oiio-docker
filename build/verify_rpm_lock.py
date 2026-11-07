#!/usr/bin/env python3
"""Fail a builder image if its installed RPM set differs from the year's lock."""

import hashlib
import os
import subprocess
import sys

QUERY_FORMAT = "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n"


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("amd64", "arm64"):
        raise SystemExit("usage: verify_rpm_lock.py cy<year> amd64|arm64")

    year, architecture = sys.argv[1], sys.argv[2]
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rpm", year,
                             "resolved-%s.packages" % architecture)
    with open(lock_path, "r") as lock_file:
        expected = lock_file.read().splitlines()
    output = subprocess.run(["rpm", "-qa", "--qf", QUERY_FORMAT], check=True, stdout=subprocess.PIPE,
                            universal_newlines=True).stdout
    actual = sorted(output.splitlines())

    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise SystemExit("installed RPM set differs from %s\nmissing: %s\nunexpected: %s"
                         % (lock_path, missing, unexpected))

    digest = hashlib.sha256(("\n".join(actual) + "\n").encode("utf-8")).hexdigest()
    print("Verified %d installed RPMs for %s %s; manifest SHA-256 %s" % (len(actual), year, architecture, digest))


if __name__ == "__main__":
    main()
