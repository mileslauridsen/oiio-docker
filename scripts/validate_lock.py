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
# Inputs used only to build or verify; everything else is compiled into, or installed in, the image.
BUILD_TOOLS = {"nasm", "cosign"}
# Every format plugin in OIIO 3.1 and 3.2 (src/*.imageio); the support contract enables or excludes each one.
OIIO_PLUGINS = {
    "bmp", "cineon", "dds", "dicom", "dpx", "ffmpeg", "fits", "gif", "hdr", "heif", "ico", "iff", "jpeg", "jpeg2000",
    "jpegxl", "null", "openexr", "openvdb", "png", "pnm", "psd", "ptex", "r3d", "raw", "rla", "sgi", "softimage",
    "targa", "term", "tiff", "webp", "zfile",
}


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
        # collect_licenses.py ships notices for every shipped entry; build tools never reach the image.
        require(item.get("shipped") is (name not in BUILD_TOOLS),
                "%s %s must set shipped to %s" % (year, name, name not in BUILD_TOOLS))
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
    require(toolchain["tools"]["g++"].startswith("gcc-toolset-%s-gcc-c++-0:%s." % (toolchain["gcc_toolset"], spec["gcc"])),
            "%s builder g++ %s differs from gcc %s" % (year, toolchain["tools"]["g++"], spec["gcc"]))
    validate_rpm_lock(year, toolchain)

    builder = "%s@%s" % (toolchain["builder_image"]["reference"], toolchain["builder_image"]["index_digest"])
    runtime = "%s@%s" % (toolchain["runtime_image"]["reference"], toolchain["runtime_image"]["index_digest"])
    expected_args = {"PLATFORM_YEAR": year, "BUILDER_IMAGE": builder, "RUNTIME_IMAGE": runtime,
                     "GCC_TOOLSET": toolchain["gcc_toolset"], "AMD64_MARCH": toolchain["cpu_baselines"]["amd64_march"],
                     "CXX_STANDARD": spec["cxx_standard"], "PYTHON_MAJOR_MINOR": spec["python"],
                     # Reproducible builds use a fixed build time in every year.
                     "SOURCE_DATE_EPOCH": "0"}
    target = targets.get(year)
    require(target is not None, "docker-bake.hcl has no %s target" % year)
    for arg, value in expected_args.items():
        require(target.get(arg) == value, "docker-bake.hcl %s %s is %s, lock says %s" % (year, arg, target.get(arg), value))
    return expected_args, len(dependencies)


def validate_rpm_lock(year, toolchain):
    rpm = toolchain["rpm"]
    minor = toolchain["builder_image"]["reference"].rsplit(":", 1)[1]
    require(toolchain["runtime_image"]["reference"].endswith(":%s-minimal" % minor),
            "%s runtime image is not the builder's Rocky %s release" % (year, minor))
    for key in ("builder_image", "runtime_image"):
        manifests = toolchain[key].get("platform_manifests", {})
        require(sorted(manifests) == list(PLATFORMS) and all(re.match(r"^sha256:[0-9a-f]{64}$", digest)
                                                             for digest in manifests.values()),
                "%s %s needs an amd64 and an arm64 manifest digest" % (year, key))

    # The repo file may name only this Rocky minor release, from pub or, once it is retired, vault.
    repo = (ROOT / "build" / rpm["repo_file"]).read_text(encoding="utf-8")
    urls = re.findall(r"https?://\S+", repo)
    require(urls and all(re.match(r"^https://dl\.rockylinux\.org/(pub|vault)/rocky/%s/" % re.escape(minor), url)
                         for url in urls), "%s repo file must name only Rocky %s over HTTPS" % (year, minor))
    require("mirrorlist" not in repo and "gpgcheck=0" not in repo,
            "%s repo file must not use mirror lists or disable package signature checks" % year)

    for platform in PLATFORMS:
        lists = {}
        for kind in ("builder", "resolved", "runtime"):
            path = ROOT / "build" / rpm["%s_packages" % kind][platform]
            lists[kind] = path.read_text(encoding="utf-8").splitlines()
            require(lists[kind] and lists[kind] == sorted(set(lists[kind])),
                    "%s %s is empty, unsorted, or has duplicates" % (year, path.relative_to(ROOT)))
        resolved = set(lists["resolved"])
        require(set(lists["builder"]) <= resolved, "%s %s builder packages are not all in the resolved set" % (year, platform))
        unpinned = [line for line in lists["builder"] if not re.match(r"^[^ ]+-\d+:[^-]+-[^-]+\.[a-z0-9_]+$", line)]
        require(not unpinned, "%s %s builder packages need an exact NEVRA: %s" % (year, platform, unpinned[:3]))
        stripped = {re.sub(r"\.[^.]+$", "", package) for package in resolved}
        for name in rpm["requested"]:
            require(any(package.startswith(name + "-") and re.match(r"^\d+:", package[len(name) + 1:])
                        for package in stripped), "%s %s requested package %s is not resolved" % (year, platform, name))
        for tool, package in toolchain["tools"].items():
            require(package in stripped, "%s %s %s %s is not in the resolved set" % (year, platform, tool, package))


def validate_build_tools(text):
    tools = json.loads((ROOT / "build" / "docker-build-tools.json").read_text(encoding="utf-8"))
    frontend = tools["dockerfile_frontend"]
    require(text.startswith("# syntax=%s@%s\n" % (frontend["reference"], frontend["index_digest"])),
            "the Dockerfile frontend differs from build/docker-build-tools.json")
    require(re.match(r"^moby/buildkit:v[\d.]+$", tools["buildkit"]["reference"]) and
            re.match(r"^sha256:[0-9a-f]{64}$", tools["buildkit"]["index_digest"]), "BuildKit must be pinned by digest")
    validate_workflow(tools)


def validate_workflow(tools):
    """Check the CI workflow pins every action, Buildx, BuildKit, and runner as recorded, and covers every year."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ci = tools["github_actions"]
    uses = re.findall(r"^[ \t]*(?:- )?uses:\s*(.*)$", text, re.MULTILINE)
    for value in uses:
        match = re.match(r"^([\w.-]+/[\w.-]+)@([0-9a-f]{40}) # (v[\d.]+)$", value)
        require(match, "workflow action is not pinned by full commit SHA with its version: %s" % value)
        expected = ci["actions"].get(match.group(1))
        require(expected == {"commit": match.group(2), "version": match.group(3)},
                "workflow action %s differs from build/docker-build-tools.json" % value)
    require({re.match(r"^([^@]+)@", value).group(1) for value in uses} == set(ci["actions"]),
            "workflow actions differ from build/docker-build-tools.json")
    buildkit = "image=%s@%s" % (tools["buildkit"]["reference"], tools["buildkit"]["index_digest"])
    for key, expected in (("version", ci["buildx_cli"]), ("driver-opts", buildkit)):
        found = re.findall(r"^[ \t]*%s:\s*(\S+)$" % key, text, re.MULTILINE)
        require(found and set(found) == {expected}, "workflow %s differs from build/docker-build-tools.json" % key)
    runners = re.findall(r"^[ \t]*runner:\s*(\S+)$", text, re.MULTILINE)
    require(sorted(set(runners)) == sorted(set(ci["runners"].values())),
            "workflow runners differ from build/docker-build-tools.json")
    for years in re.findall(r"^[ \t]*year:\s*\[([^\]]*)\]$", text, re.MULTILINE):
        require(tuple(year.strip() for year in years.split(",")) == YEARS, "workflow matrix years differ from the locks")
    require(re.search(r"^[ \t]*year:", text, re.MULTILINE), "workflow has no year matrix")
    require(re.findall(r"^[ \t]*permissions:.*$", text, re.MULTILINE) == ["permissions:"] and
            "\npermissions:\n  contents: read\n\n" in text, "workflow must grant only contents: read")


def validate_dockerfile(current_args):
    text, defaults = dockerfile_defaults()
    for arg, value in current_args.items():
        require(defaults.get(arg) == value, "Dockerfile default %s is %s, the %s lock says %s" %
                (arg, defaults.get(arg), CURRENT_YEAR, value))
    body = "\n".join(line for line in text.splitlines() if not line.startswith("# syntax="))
    require(re.search(r"https?://", body) is None, "the Dockerfile must not name source URLs; locks own them")
    require("--network=none" in text, "compile steps must run without network access")
    require(re.search(r"\bdnf\b[^\n]*\b(update|upgrade)\b", text) is None, "the Dockerfile must not run dnf update or upgrade")
    require("verify_rpm_lock.py" in text, "the builder must verify its installed RPM set")
    validate_build_tools(text)
    validate_image_support(text)


def validate_image_support(text):
    """Check build/image-support.json covers every OIIO plugin, matches the Dockerfile, and matches the fixtures."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import generate_test_images

    contract = json.loads((ROOT / "build" / "image-support.json").read_text(encoding="utf-8"))
    enabled = set(contract["formats"])
    excluded = {item["format"]: item["cmake"] for item in contract["excluded_formats"]}
    require(not enabled & set(excluded), "formats both enabled and excluded: %s" % sorted(enabled & set(excluded)))
    require(enabled | set(excluded) == OIIO_PLUGINS, "the support contract does not cover exactly OIIO's plugins: %s"
            % sorted(OIIO_PLUGINS ^ (enabled | set(excluded))))
    for name, option in sorted(excluded.items()):
        require(re.search(r"-D%s=OFF\b" % re.escape(option), text), "the Dockerfile does not disable %s (-D%s=OFF)"
                % (name, option))
    require(set(contract["ocio"]) == set(YEARS), "the support contract's OCIO years differ from the locks")
    with tempfile.TemporaryDirectory(prefix="oiio-fixtures-") as directory:
        generated = generate_test_images.generate(pathlib.Path(directory))
    require(generated == contract["fixtures"], "generated fixtures differ from build/image-support.json")
    require(generate_test_images.derived_hashes() == contract["derived_pixel_sha1"],
            "derived pixel hashes differ from build/image-support.json")


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
        print("CI workflow pins match build/docker-build-tools.json and cover every year")
        print("Image support contract covers every OIIO plugin and matches the Dockerfile and fixtures")
        validate_rejections()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print("lock validation failed: %s" % error, file=sys.stderr)
        sys.exit(1)
