#!/usr/bin/env python3
"""Validate every platform-year lock and prove bad archives and signatures are rejected before extraction."""

import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
YEARS = ("cy2025", "cy2026", "cy2027")
CURRENT_YEAR = "cy2026"
PLATFORMS = ("linux/amd64", "linux/arm64")
COMMON_SOURCES = {
    "nasm", "zlib", "libjpeg-turbo", "libpng", "libtiff", "cpython", "imath", "openexr", "expat", "yaml-cpp",
    "pystring", "minizip-ng", "sse2neon", "pybind11", "opencolorio", "fmt", "robin-map", "openimageio",
}
# Sources only some years need: OpenEXR 3.3 clones libdeflate, and OIIO 3.2 binds Python with nanobind.
YEAR_SOURCES = {"cy2025": {"libdeflate"}, "cy2026": set(), "cy2027": {"nanobind"}}
# Specification keys checked against the series of the locked version.
SPEC_SERIES = {"python": "cpython", "numpy": "numpy", "opencolorio": "opencolorio", "openexr": "openexr", "imath": "imath"}
# Projects that publish signatures for the locked files; every year must verify them.
SIGNED = {"zlib": "gpg", "libjpeg-turbo": "gpg", "libtiff": "gpg", "cpython": "gpg", "expat": "gpg",
          "imath": "sigstore", "openexr": "sigstore", "opencolorio": "sigstore", "openimageio": "sigstore"}
# Releases that publish no signed artifact, recorded so the exception stays deliberate.
UNSIGNED_EXCEPTIONS = {("opencolorio", "2.4.2")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_fetch_helper():
    spec = importlib.util.spec_from_file_location("fetch_sources", ROOT / "build" / "fetch_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def key_fingerprints(path):
    gpg = shutil.which("gpg2") or shutil.which("gpg")
    require(gpg, "gpg is required to check pinned key files")
    output = subprocess.run([gpg, "--batch", "--show-keys", "--with-colons", str(path)], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, universal_newlines=True, check=True).stdout
    return {line.split(":")[9] for line in output.splitlines() if line.startswith("fpr:")}


def series(version, parts=2):
    return ".".join(version.split(".")[:parts])


def bake_targets():
    text = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")
    targets = {}
    for name, body in re.findall(r'target "(\w+)" \{(.*?)\n\}', text, re.S):
        targets[name] = dict(re.findall(r'^\s*(\w+)\s*=\s*"([^"]*)"', body, re.M))
    return targets


def dockerfile_defaults():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    return text, dict(re.findall(r"^ARG (\w+)=(\S+)$", text, re.M))


def validate_year(year, helper, targets, key_cache):
    path = ROOT / "build" / "locks" / (year + ".json")
    lock = json.loads(path.read_text(encoding="utf-8"))
    dependencies = helper.load_lock(str(path))
    require(lock.get("platform_year") == year.upper(), "%s: platform_year differs from the file name" % year)
    spec, toolchain = lock["specification"], lock["toolchain"]

    by_name, sources = {}, set()
    for item in dependencies:
        name, kind = item["name"], item.get("kind", "source")
        require(item.get("version"), "%s %s has no version" % (year, name))
        require(item.get("role"), "%s %s has no role" % (year, name))
        require(item.get("checksum_provenance"), "%s %s has no checksum provenance" % (year, name))
        by_name.setdefault(name, []).append(item)
        if kind == "source":
            sources.add(name)
        for signature in item.get("signatures", []):
            if signature["type"] == "gpg":
                key = ROOT / "build" / signature["key_file"]
                require(key.is_file(), "%s %s signing key is missing: %s" % (year, name, signature["key_file"]))
                if key not in key_cache:
                    key_cache[key] = key_fingerprints(key)
                require(signature["fingerprint"] in key_cache[key],
                        "%s %s fingerprint is not in %s" % (year, name, signature["key_file"]))
            else:
                tag = "@refs/tags/v" + item["version"]
                require(signature["certificate_identity"].endswith(tag),
                        "%s %s Sigstore identity is not for tag v%s" % (year, name, item["version"]))
                root = ROOT / "build" / signature["trusted_root"]
                require(root.is_file(), "%s %s Sigstore trusted root is missing: %s" % (year, name, signature["trusted_root"]))
                require(hashlib.sha256(root.read_bytes()).hexdigest() == signature["trusted_root_sha256"],
                        "%s %s Sigstore trusted root differs from its pinned SHA-256" % (year, name))

    expected = COMMON_SOURCES | YEAR_SOURCES[year]
    require(sources == expected, "%s source set differs: missing %s, unexpected %s" %
            (year, sorted(expected - sources), sorted(sources - expected)))
    for name, kind in (("numpy", "wheel"), ("cosign", "tool")):
        platforms = sorted(item.get("platform") for item in by_name.get(name, []) if item.get("kind") == kind)
        require(platforms == list(PLATFORMS), "%s needs one %s %s per platform, got %s" % (year, name, kind, platforms))
        require(len({item["version"] for item in by_name[name]}) == 1, "%s %s versions differ by platform" % (year, name))
    for name, kind in SIGNED.items():
        item = by_name[name][0]
        if (name, item["version"]) in UNSIGNED_EXCEPTIONS:
            require(not item.get("signatures"), "%s %s %s is a recorded unsigned exception" % (year, name, item["version"]))
            continue
        require([s["type"] for s in item.get("signatures", [])] == [kind],
                "%s %s must carry one %s signature" % (year, name, kind))

    for key, name in SPEC_SERIES.items():
        version = by_name[name][0]["version"]
        require(series(version) == spec[key], "%s %s %s is not in the specified %s series" % (year, name, version, spec[key]))
    require(toolchain["gcc_toolset"] == spec["gcc"].split(".")[0], "%s gcc-toolset differs from the specified gcc" % year)
    require(any(package.startswith("gcc-toolset-%s-gcc-c++-%s" % (toolchain["gcc_toolset"], spec["gcc"]))
                for package in toolchain["builder_packages"]), "%s builder gcc package differs from gcc %s" % (year, spec["gcc"]))

    builder = "%s@%s" % (toolchain["builder_image"]["reference"], toolchain["builder_image"]["index_digest"])
    runtime = "%s@%s" % (toolchain["runtime_image"]["reference"], toolchain["runtime_image"]["index_digest"])
    expected_args = {"PLATFORM_YEAR": year, "BUILDER_IMAGE": builder, "RUNTIME_IMAGE": runtime,
                     "GCC_TOOLSET": toolchain["gcc_toolset"], "CXX_STANDARD": spec["cxx_standard"],
                     "PYTHON_MAJOR_MINOR": spec["python"]}
    target = targets.get(year)
    require(target is not None, "docker-bake.hcl has no %s target" % year)
    for arg, value in expected_args.items():
        require(target.get(arg) == value, "docker-bake.hcl %s %s is %s, lock says %s" % (year, arg, target.get(arg), value))
    return expected_args, len(dependencies)


def validate_dockerfile(current_args):
    text, defaults = dockerfile_defaults()
    for arg, value in current_args.items():
        require(defaults.get(arg) == value, "Dockerfile default %s is %s, the %s lock says %s" %
                (arg, defaults.get(arg), CURRENT_YEAR, value))
    body = "\n".join(line for line in text.splitlines() if not line.startswith("# syntax="))
    require(re.search(r"https?://", body) is None, "the Dockerfile must not name source URLs; locks own them")
    require("--network=none" in text, "compile steps must run without network access")


def rejection(arguments, expected_text, extraction):
    result = subprocess.run([sys.executable, str(ROOT / "build" / "fetch_sources.py")] + arguments,
                            universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode != 0, "a bad input was accepted: %s" % " ".join(arguments))
    require(expected_text in result.stdout, "bad input failed for an unexpected reason:\n%s" % result.stdout)
    require(not extraction.exists(), "source extraction started before the input was rejected")


def validate_rejections():
    with tempfile.TemporaryDirectory(prefix="oiio-lock-check-") as temporary:
        directory = pathlib.Path(temporary)
        lock = str(ROOT / "build" / "locks" / (CURRENT_YEAR + ".json"))

        # Corrupt bytes fail their checksum before anything is extracted.
        bad_archive = directory / "corrupt.tar.xz"
        bad_archive.write_bytes(b"deliberately incorrect archive\n")
        rejection(["--lockfile", lock, "--platform", "linux/arm64", "--verify-archive", "zlib",
                   "--archive", str(bad_archive), "--extract-dir", str(directory / "extracted-checksum")],
                  "SHA-256 mismatch", directory / "extracted-checksum")

        # Bytes that pass their checksum still fail a bad GPG signature before extraction.
        archive = directory / "zlib-test.tar.xz"
        archive.write_bytes(b"checksum-matching test archive\n")
        zlib = next(item for item in json.loads(pathlib.Path(lock).read_text(encoding="utf-8"))["dependencies"]
                    if item["name"] == "zlib")
        test_lock = {"lock_version": 1, "dependencies": [dict(zlib, archive=archive.name, sha256=hashlib.sha256(
            archive.read_bytes()).hexdigest(), signatures=[dict(zlib["signatures"][0], file="zlib-test.tar.xz.asc")])]}
        (directory / "test-lock.json").write_text(json.dumps(test_lock), encoding="utf-8")
        (directory / "zlib-test.tar.xz.asc").write_text("-----BEGIN PGP SIGNATURE-----\n\ninvalid\n"
                                                        "-----END PGP SIGNATURE-----\n", encoding="utf-8")
        rejection(["--lockfile", str(directory / "test-lock.json"), "--platform", "linux/arm64",
                   "--verify-archive", "zlib", "--archive", str(archive), "--extract-dir",
                   str(directory / "extracted-signature")],
                  "detached signature verification failed", directory / "extracted-signature")

        # A Sigstore entry whose pinned trust root does not match fails before cosign runs.
        imath = next(item for item in json.loads(pathlib.Path(lock).read_text(encoding="utf-8"))["dependencies"]
                     if item["name"] == "imath")
        imath_archive = directory / "imath-test.tar.gz"
        imath_archive.write_bytes(b"checksum-matching test archive\n")
        root_lock = {"lock_version": 1, "dependencies": [dict(imath, archive=imath_archive.name, sha256=hashlib.sha256(
            imath_archive.read_bytes()).hexdigest(), signatures=[dict(imath["signatures"][0], file="imath-test.sigstore.json",
                                                                     trusted_root_sha256="0" * 64)])]}
        (directory / "root-lock.json").write_text(json.dumps(root_lock), encoding="utf-8")
        (directory / "imath-test.sigstore.json").write_text("{}\n", encoding="utf-8")
        rejection(["--lockfile", str(directory / "root-lock.json"), "--platform", "linux/arm64",
                   "--verify-archive", "imath", "--archive", str(imath_archive), "--extract-dir",
                   str(directory / "extracted-trusted-root")],
                  "Sigstore trusted root SHA-256 mismatch", directory / "extracted-trusted-root")
    print("Verified checksum, GPG signature, and Sigstore trusted root rejection before extraction")


if __name__ == "__main__":
    try:
        helper = load_fetch_helper()
        targets, key_cache, current = bake_targets(), {}, None
        for year in YEARS:
            args, count = validate_year(year, helper, targets, key_cache)
            if year == CURRENT_YEAR:
                current = args
            print("%s: %d locked inputs consistent with the specification and docker-bake.hcl" % (year, count))
        require(set(targets) == set(YEARS), "docker-bake.hcl targets differ from the locks: %s" % sorted(targets))
        validate_dockerfile(current)
        print("Dockerfile defaults match %s and name no sources" % CURRENT_YEAR)
        validate_rejections()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print("lock validation failed: %s" % error, file=sys.stderr)
        sys.exit(1)
