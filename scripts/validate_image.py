#!/usr/bin/env python3
"""Check a platform-year image against its lock: versions, glibc ceiling, linkage, contents, licenses, and size."""

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHT_SYMTAB = 2
SHT_GNU_VERDEF = 0x6FFFFFFD
SHT_GNU_VERNEED = 0x6FFFFFFE
EXCLUDED_LIBRARY_PATTERNS = ("libQt", "libboost", "libtbb", "libopenvdb", "libPtex", "libraw", "libavcodec")
# NumPy's wheel ships C headers, static helper libraries, a pkg-config file, and a numpy-config script for building
# extensions, and its binaries keep their symbol tables. It is installed unchanged, so its files are exempt.
NUMPY_PACKAGE = re.compile(r"/site-packages/numpy(\.libs)?/")

# Runs in the image: build tools on the PATH directories, build-stage directories, development files outside
# NumPy, and the shell and user the README relies on.
CONTENTS = r"""
import json, os, pwd, re, shutil
path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/vfx/bin"
tools = sorted(name for name in ("gcc", "g++", "cc", "c++", "cpp", "clang", "ld", "as", "ar", "make", "cmake",
                                  "ninja", "nasm", "pkg-config", "pkgconf", "strip", "objcopy", "objdump", "gdb")
               if shutil.which(name, path=path))
for directory in path.split(":"):
    if os.path.isdir(directory):
        tools += sorted(name for name in os.listdir(directory)
                        if re.match(r"^(.+-)?(gcc|g\+\+|c\+\+|ld)(-[\d.]+)?$", name))
directories = [d for d in ("/src", "/opt/deps", "/opt/build-tools", "/opt/rh", "/opt/vfx-debug", "/opt/vfx/include")
               if os.path.exists(d)]
development = []
for top in ("/opt/vfx", "/usr/include", "/usr/local"):
    for root, _dirs, files in os.walk(top):
        for name in files:
            full = os.path.join(root, name)
            if re.search(r"\.(h|hh|hpp|hxx|inl|a|la|pc|cmake)$", name) and not re.search(NUMPY, full):
                development.append(full)
# Build-configuration scripts such as libpng-config, which describe headers the image does not ship.
if os.path.isdir("/opt/vfx/bin"):
    development += sorted(os.path.join("/opt/vfx/bin", name) for name in os.listdir("/opt/vfx/bin")
                          if name.endswith("-config") and name != "numpy-config")
user = pwd.getpwnam("algernon")
print(json.dumps({"tools": sorted(set(tools)), "directories": directories, "development": sorted(development),
                  "bash": os.access("/bin/bash", os.X_OK),
                  "user": [user.pw_uid, user.pw_gid, user.pw_dir, os.stat(user.pw_dir).st_uid]}))
""".replace("NUMPY", repr(NUMPY_PACKAGE.pattern))


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


def elf_has_symtab(path):
    """Whether an ELF64 little-endian file still has a symbol table section, that is, is not stripped."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return False
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    return any(struct.unpack_from("<I", data, shoff + index * shentsize + 4)[0] == SHT_SYMTAB
               for index in range(shnum))


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
    parser.add_argument("--lockfile", help="lock to check against (default: build/locks/<year>.json)")
    parser.add_argument("--metadata", help="write results as JSON to this path")
    args = parser.parse_args()

    with open(args.lockfile or os.path.join(REPO, "build", "locks", args.year + ".json")) as lock_file:
        lock = json.load(lock_file)
    pins, shipped = {}, {}
    for dependency in lock["dependencies"]:
        pins[dependency["name"]] = dependency["version"]
        if dependency["shipped"] and dependency.get("platform", args.platform) == args.platform:
            shipped[dependency["name"]] = dependency["version"]
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
    # OIIO 3.2 and later bind Python with nanobind; earlier releases use pybind11.
    bindings = "nanobind" if "nanobind" in pins else "pybind11"
    for reported, pin in (("Imath", "imath"), ("OpenColorIO", "opencolorio"), ("OpenEXR", "openexr"),
                          ("libjpeg-turbo", "libjpeg-turbo"), ("PNG", "libpng"), ("TIFF", "libtiff"),
                          ("ZLIB", "zlib"), ("fmt", "fmt"), (bindings, bindings), ("Python3", "cpython")):
        check.expect("OIIO built with {0}".format(reported), dependencies.get(reported), pins[pin])
    check.expect("python version", check.docker("python3", "--version").strip().split()[1], pins["cpython"])
    probe = (
        "import json, os, re, numpy, OpenImageIO as oiio, PyOpenColorIO as ocio\n"
        "assert numpy.allclose(numpy.linalg.inv(numpy.eye(3) * 2.0), numpy.eye(3) * 0.5)\n"
        "imath = [m.group(1) + '.' + m.group(2) for m in (re.match(r'libImath-(\\d+)_(\\d+)\\.so$', f)"
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
    # Imath's library file names carry its series (libImath-3_1.so); the exact release comes from --buildinfo.
    check.expect("installed Imath library series", versions["imath"], [".".join(pins["imath"].split(".")[:2])])
    libraries = versions["libraries"]
    check.results["library_list"] = libraries
    # library_list names the format libraries OIIO loaded; OCIO is checked above through opencolorio_version.
    for label, pattern, pin in (("OpenEXR", r"OpenEXR ([\d.]+)", "openexr"), ("libtiff", r"LIBTIFF Version ([\d.]+)", "libtiff"),
                                ("libjpeg-turbo", r"jpeg-turbo ([\d.]+)", "libjpeg-turbo"), ("libpng", r"libpng ([\d.]+)", "libpng")):
        match = re.search(pattern, libraries)
        check.expect("OIIO {0} dependency".format(label), match.group(1) if match else None, pins[pin])
    glibc = re.search(r"([\d.]+)\s*$", check.docker("ldd", "--version").splitlines()[0]).group(1)
    check.expect("runtime glibc", glibc, spec["glibc"])
    # The runtime stage installs no RPMs, so its package set is the digest-pinned base image's.
    runtime_lock = os.path.join(REPO, "build", lock["toolchain"]["rpm"]["runtime_packages"][args.platform])
    with open(runtime_lock) as runtime_file:
        expected_rpms = runtime_file.read().splitlines()
    actual_rpms = sorted(check.docker("rpm", "-qa", "--qf", "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n").splitlines())
    check.expect("runtime RPM set matches lock", actual_rpms == expected_rpms, True)
    if actual_rpms != expected_rpms:
        print("  missing: {0}\n  unexpected: {1}".format(sorted(set(expected_rpms) - set(actual_rpms)),
                                                       sorted(set(actual_rpms) - set(expected_rpms))))

    work = tempfile.mkdtemp(prefix="oiio-validate-")
    os.chmod(work, 0o777)
    container = run(["docker", "create", "--platform", args.platform, args.image]).strip()
    try:
        run(["docker", "cp", container + ":/opt/vfx", os.path.join(work, "vfx")])
        run(["docker", "cp", "-L", container + ":/usr/lib64/libstdc++.so.6", os.path.join(work, "libstdc++.so.6")])
    finally:
        run(["docker", "rm", container])
    libstdcxx_max = max_version(elf_symbol_versions(os.path.join(work, "libstdc++.so.6"))[1], "GLIBCXX_")
    worst_glibc, worst_glibcxx, excluded, unstripped, elf_count = "GLIBC_0", "GLIBCXX_0", [], [], 0
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
            elf_count += 1
            if elf_has_symtab(path) and not NUMPY_PACKAGE.search(path):
                unstripped.append(os.path.relpath(path, work))
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
    check.expect("unstripped ELF files outside NumPy", unstripped, [])
    print("INFO {0} shipped ELF files".format(elf_count))

    contents = json.loads(check.docker("python3", "-c", CONTENTS).strip().splitlines()[-1])
    check.expect("compilers and build tools present", contents["tools"], [])
    check.expect("build-stage directories present", contents["directories"], [])
    check.expect("headers, static archives, and build configs outside NumPy", contents["development"], [])
    check.expect("bash present", contents["bash"], True)
    check.expect("algernon user (uid, gid, home, home owner)", contents["user"], [1000, 1000, "/home/algernon", 1000])

    # Every shipped component's notices are in /opt/vfx/share/licenses, listed with their hashes in
    # components.json; the Rocky runtime libraries' notices are the base image's own.
    licenses = os.path.join(work, "vfx", "share", "licenses")
    with open(os.path.join(licenses, "components.json")) as manifest_file:
        manifest = json.load(manifest_file)
    listed = {component["name"]: component["version"] for component in manifest["components"]}
    check.expect("license manifest components match the lock", listed, shipped)
    problems = []
    for component in manifest["components"]:
        if not component["files"]:
            problems.append(component["name"] + ": no files")
        for entry in component["files"]:
            path = os.path.join(licenses, entry["path"])
            if not os.path.isfile(path):
                problems.append(entry["path"] + ": missing")
                continue
            with open(path, "rb") as notice:
                if hashlib.sha256(notice.read()).hexdigest() != entry["sha256"]:
                    problems.append(entry["path"] + ": hash differs")
    check.expect("license files present and matching the manifest", problems, [])
    print("INFO {0} license and notice files for {1} components".format(
        sum(len(component["files"]) for component in manifest["components"]), len(listed)))
    rocky = check.docker("ls", "/usr/share/licenses").split()
    check.expect("Rocky glibc and libgcc license files present", [name for name in ("glibc", "libgcc") if name in rocky],
                 ["glibc", "libgcc"])

    # The minimal runtime has no find, so walk /opt/vfx with the image's own Python and ldd each ELF file.
    # Libraries that wheels bundle in a *.libs directory rely on the extension that loads them for their
    # neighbours' search path, so resolve those from their own directory.
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
        "        env = dict(os.environ, LD_LIBRARY_PATH=root) if root.endswith('.libs') else None\n"
        "        out = subprocess.run(['ldd', path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,"
        " universal_newlines=True, env=env).stdout\n"
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

    # Budget the unpacked size: the sum of the layer sizes. With the containerd image store, .Size also
    # counts the compressed layers, and before an image is unpacked it counts only those.
    inspect = json.loads(run(["docker", "image", "inspect", args.image]))[0]
    layers = [int(size) for size in run(["docker", "history", "--human=false", "--format", "{{.Size}}",
                                          args.image]).split()]
    unpacked = sum(layers)
    check.results["image"] = {"id": inspect["Id"], "unpacked_size": unpacked, "reported_size": inspect["Size"]}
    print("INFO image {0} unpacked size {1} bytes (docker image inspect .Size {2})".format(
        inspect["Id"], unpacked, inspect["Size"]))
    with open(os.path.join(REPO, "build", "image-size-budgets.json")) as budget_file:
        budget = json.load(budget_file)["budgets"].get(args.year, {}).get(args.platform)
    check.expect("image size within budget", budget is not None and 0 < unpacked <= budget, True)

    if args.metadata:
        with open(args.metadata, "w") as output:
            json.dump({"image": args.image, "platform": args.platform, "year": args.year,
                       "failures": check.failures, "results": check.results}, output, indent=2, sort_keys=True)
    print("{0}: {1} failure(s)".format(args.image, len(check.failures)))
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
