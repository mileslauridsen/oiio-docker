#!/usr/bin/env python3
"""Check a platform-year image against its lock: versions, glibc ceiling, linkage, contents, and image I/O."""

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHT_GNU_VERDEF = 0x6FFFFFFD
SHT_GNU_VERNEED = 0x6FFFFFFE
EXCLUDED_LIBRARY_PATTERNS = ("libQt", "libboost", "libtbb", "libopenvdb", "libPtex", "libraw", "libavcodec")


def run(args, check=True):
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if check and process.returncode != 0:
        raise RuntimeError("command failed ({0}): {1}\n{2}".format(process.returncode, " ".join(args), process.stdout))
    return process.stdout


def version_key(text):
    return tuple(int(part) for part in re.findall(r"\d+", text))


def elf_symbol_versions(path):
    """Return (required, defined) GNU symbol version names from an ELF64 little-endian file."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + index * shentsize) for index in range(shnum)]

    def string(section_index, offset):
        start = sections[section_index][4] + offset
        return data[start:data.index(b"\0", start)].decode("ascii", "replace")

    required, defined = set(), set()
    for _name, kind, _flags, _addr, offset, _size, link, info, _align, _entsize in sections:
        if kind == SHT_GNU_VERNEED:
            entry = offset
            for _ in range(info):
                _version, count, _file, aux, following = struct.unpack_from("<HHIII", data, entry)
                aux_entry = entry + aux
                for _ in range(count):
                    _hash, _flags2, _other, name, next_aux = struct.unpack_from("<IHHII", data, aux_entry)
                    required.add(string(link, name))
                    aux_entry += next_aux
                entry += following
        elif kind == SHT_GNU_VERDEF:
            entry = offset
            for _ in range(info):
                _version, _flags2, _index, count, _hash, aux, following = struct.unpack_from("<HHHHIII", data, entry)
                if count:
                    name, = struct.unpack_from("<I", data, entry + aux)
                    defined.add(string(link, name))
                entry += following
    return required, defined


def max_version(names, prefix):
    versions = [name for name in names if name.startswith(prefix) and re.match(r"^" + prefix + r"[\d.]+$", name)]
    return max(versions, key=version_key) if versions else None


class Checker:
    def __init__(self, image, platform):
        self.image = image
        self.platform = platform
        self.failures = []
        self.results = {}

    def docker(self, entrypoint, *args, mount=None):
        command = ["docker", "run", "--rm", "--platform", self.platform]
        if mount:
            command += ["-v", "{0}:/work".format(mount), "-w", "/work"]
        command += ["--entrypoint", entrypoint, self.image] + list(args)
        return run(command)

    def expect(self, label, actual, expected):
        ok = actual == expected
        self.results[label] = {"actual": actual, "expected": expected, "ok": ok}
        print("{0} {1}: {2}{3}".format("PASS" if ok else "FAIL", label, actual, "" if ok else " (expected {0})".format(expected)))
        if not ok:
            self.failures.append(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", required=True, choices=("linux/amd64", "linux/arm64"))
    parser.add_argument("--year", required=True, help="platform year lock name, for example cy2026")
    parser.add_argument("--metadata", help="write results as JSON to this path")
    args = parser.parse_args()

    with open(os.path.join(REPO, "build", "locks", args.year + ".json")) as lock_file:
        lock = json.load(lock_file)
    pins = {}
    for dependency in lock["dependencies"]:
        pins[dependency["name"]] = dependency["version"]
    spec = lock["specification"]
    check = Checker(args.image, args.platform)

    inspect = json.loads(run(["docker", "image", "inspect", args.image]))[0]
    check.expect("image architecture", "linux/" + inspect["Architecture"], args.platform)
    check.expect("image user", inspect["Config"].get("User"), "algernon")

    buildinfo = check.docker("oiiotool", "--buildinfo")
    check.results["buildinfo"] = buildinfo
    check.expect("oiiotool version", re.search(r"^OIIO ([\d.]+)", buildinfo, re.M).group(1), pins["openimageio"])
    compiler = re.search(r"Build compiler: gcc ([\d]+\.[\d]+) \| C\+\+(\d+)", buildinfo)
    check.expect("build compiler", compiler.group(1) if compiler else None, spec["gcc"])
    check.expect("build C++ standard", compiler.group(2) if compiler else None, spec["cxx_standard"])
    simd = re.search(r"HW features enabled at build: (.*)", buildinfo)
    print("INFO OIIO build SIMD: {0}".format(simd.group(1).strip() if simd else "unknown"))
    dependencies = dict(re.findall(r"([A-Za-z][\w-]*) ([\d][\d.]*)", buildinfo.split("Dependencies:", 1)[-1]))
    for reported, pin in (("Imath", "imath"), ("OpenColorIO", "opencolorio"), ("OpenEXR", "openexr"),
                          ("libjpeg-turbo", "libjpeg-turbo"), ("PNG", "libpng"), ("TIFF", "libtiff"),
                          ("ZLIB", "zlib"), ("fmt", "fmt"), ("pybind11", "pybind11"), ("Python3", "cpython")):
        check.expect("OIIO built with {0}".format(reported), dependencies.get(reported), pins[pin])
    check.expect("python version", check.docker("python3", "--version").strip().split()[1], pins["cpython"])
    probe = (
        "import json, os, re, numpy, OpenImageIO as oiio, PyOpenColorIO as ocio\n"
        "imath = [m.group(1) for m in (re.match(r'libImath-\\d+_\\d+\\.so\\.\\d+\\.([\\d.]+)$', f)"
        " for f in os.listdir('/opt/vfx/lib')) if m]\n"
        "print(json.dumps({'numpy': numpy.__version__, 'oiio': oiio.__version__, 'ocio': ocio.__version__,"
        " 'oiio_ocio': oiio.get_string_attribute('opencolorio_version'), 'imath': imath,"
        " 'libraries': oiio.get_string_attribute('library_list')}))\n"
    )
    versions = json.loads(check.docker("python3", "-c", probe).strip().splitlines()[-1])
    check.expect("numpy version", versions["numpy"], pins["numpy"])
    check.expect("python OpenImageIO version", versions["oiio"], pins["openimageio"])
    check.expect("python PyOpenColorIO version", versions["ocio"], pins["opencolorio"])
    check.expect("OIIO OpenColorIO dependency", versions["oiio_ocio"], pins["opencolorio"])
    check.expect("installed Imath library", versions["imath"], [pins["imath"]])
    libraries = versions["libraries"]
    check.results["library_list"] = libraries
    match = re.search(r"OpenEXR ([\d.]+)", libraries)
    check.expect("OIIO OpenEXR dependency", match.group(1) if match else None, pins["openexr"])
    glibc = re.search(r"([\d.]+)\s*$", check.docker("ldd", "--version").splitlines()[0]).group(1)
    check.expect("runtime glibc", glibc, spec["glibc"])

    work = tempfile.mkdtemp(prefix="oiio-validate-")
    os.chmod(work, 0o777)
    container = run(["docker", "create", "--platform", args.platform, args.image]).strip()
    try:
        run(["docker", "cp", container + ":/opt/vfx", os.path.join(work, "vfx")])
        run(["docker", "cp", "-L", container + ":/usr/lib64/libstdc++.so.6", os.path.join(work, "libstdc++.so.6")])
    finally:
        run(["docker", "rm", container])
    libstdcxx_max = max_version(elf_symbol_versions(os.path.join(work, "libstdc++.so.6"))[1], "GLIBCXX_")
    worst_glibc, worst_glibcxx, excluded = "GLIBC_0", "GLIBCXX_0", []
    for root, _dirs, files in os.walk(os.path.join(work, "vfx")):
        for name in files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            if name.startswith(EXCLUDED_LIBRARY_PATTERNS):
                excluded.append(os.path.relpath(path, work))
            versions_found = elf_symbol_versions(path)
            if not versions_found:
                continue
            for prefix, current in (("GLIBC_", worst_glibc), ("GLIBCXX_", worst_glibcxx)):
                highest = max_version(versions_found[0], prefix)
                if highest and version_key(highest) > version_key(current):
                    if prefix == "GLIBC_":
                        worst_glibc = highest
                    else:
                        worst_glibcxx = highest
    check.expect("highest GLIBC symbol within floor", version_key(worst_glibc) <= version_key(spec["glibc"]), True)
    check.expect("highest GLIBCXX symbol within base libstdc++", version_key(worst_glibcxx) <= version_key(libstdcxx_max), True)
    check.results["symbol_versions"] = {"glibc": worst_glibc, "glibcxx": worst_glibcxx, "base_libstdcxx": libstdcxx_max}
    print("INFO highest required {0} and {1}; base libstdc++ provides {2}".format(worst_glibc, worst_glibcxx, libstdcxx_max))
    check.expect("excluded platform libraries present", excluded, [])

    # The minimal runtime has no find, so walk /opt/vfx with the image's own Python and ldd each ELF file.
    linkage = (
        "import os, subprocess\n"
        "count = 0\n"
        "for root, dirs, files in os.walk('/opt/vfx'):\n"
        "    for name in files:\n"
        "        path = os.path.join(root, name)\n"
        "        if os.path.islink(path):\n"
        "            continue\n"
        "        with open(path, 'rb') as handle:\n"
        "            if handle.read(4) != b'\\x7fELF':\n"
        "                continue\n"
        "        count += 1\n"
        "        out = subprocess.run(['ldd', path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,"
        " universal_newlines=True).stdout\n"
        "        for line in out.splitlines():\n"
        "            if 'not found' in line:\n"
        "                print('MISSING', path, line.strip())\n"
        "print('CHECKED', count)\n"
    )
    output = check.docker("python3", "-c", linkage).strip().splitlines()
    print("INFO ldd checked {0} ELF files".format(output[-1].split()[-1]))
    check.expect("unresolved shared libraries", [line for line in output if line.startswith("MISSING")], [])

    io_dir = os.path.join(work, "io")
    os.mkdir(io_dir)
    os.chmod(io_dir, 0o777)
    for ext, fmt in (("exr", "half"), ("tif", "uint16"), ("png", "uint8"), ("jpg", "uint8")):
        check.docker("oiiotool", "--pattern", "checker", "128x128", "3", "-d", fmt, "-o", "smoke." + ext, mount=io_dir)
        info = check.docker("iinfo", "smoke." + ext, mount=io_dir).strip()
        check.expect("{0} round trip".format(ext), bool(re.search(r"128 x\s+128, 3 channel", info)), True)
    check.docker("maketx", "smoke.exr", "-o", "smoke.tx", mount=io_dir)
    check.expect("maketx MIP levels", "MIP-map levels" in check.docker("iinfo", "-v", "smoke.tx", mount=io_dir), True)
    read = check.docker(
        "python3", "-c",
        "import OpenImageIO as oiio; s = oiio.ImageBuf('smoke.exr').spec(); "
        "a = oiio.ImageBuf('smoke.exr').get_pixels(oiio.FLOAT); print(s.width, s.height, s.nchannels, s.format, a.shape)",
        mount=io_dir,
    ).strip()
    check.expect("python EXR read", read, "128 128 3 half (128, 128, 3)")
    colour = check.docker(
        "python3", "-c",
        "import PyOpenColorIO as ocio; c = ocio.Config.CreateFromFile('ocio://default'); "
        "p = c.getProcessor('ACES2065-1', 'ACEScg').getDefaultCPUProcessor(); "
        "print(c.getName()); print(round(p.applyRGB([0.5, 0.2, 0.1])[0], 4) != 0.5)",
    ).strip().splitlines()
    check.results["ocio_builtin_config"] = colour[0]
    print("INFO OCIO built-in default config: {0}".format(colour[0]))
    check.expect("OCIO ACES2065-1 to ACEScg conversion", colour[-1], "True")

    # Measure after containers have run: Docker Desktop reports only compressed content for a
    # freshly loaded image whose platform differs from the engine's until it is unpacked.
    inspect = json.loads(run(["docker", "image", "inspect", args.image]))[0]
    check.results["image"] = {"id": inspect["Id"], "size": inspect["Size"]}
    print("INFO image {0} size {1} bytes".format(inspect["Id"], inspect["Size"]))
    with open(os.path.join(REPO, "build", "image-size-budgets.json")) as budget_file:
        budget = json.load(budget_file)["budgets"].get(args.year, {}).get(args.platform)
    check.expect("image size within budget", budget is not None and inspect["Size"] <= budget, True)

    if args.metadata:
        with open(args.metadata, "w") as output:
            json.dump({"image": args.image, "platform": args.platform, "year": args.year,
                       "failures": check.failures, "results": check.results}, output, indent=2, sort_keys=True)
    print("{0}: {1} failure(s)".format(args.image, len(check.failures)))
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
