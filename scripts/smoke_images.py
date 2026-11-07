#!/usr/bin/env python3
"""Check a built image against the image support contract: format round trips, maketx, OCIO, and Python I/O."""

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

from generate_test_images import derived_hashes, generate as generate_fixtures

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = re.compile(r"(\d+) x\s+(\d+), (\d+) channel, (\S+) (\S+)")
SUBIMAGE = re.compile(r"^ subimage\s+\d+:")
# ACES2065-1 (AP0) to ACEScg (AP1). Both use the ACES white point, so the conversion is this matrix alone.
AP0_TO_AP1 = [[1.4514393161, -0.2365107469, -0.2149285693],
              [-0.0765537734, 1.1762296998, -0.0996759264],
              [0.0083161484, -0.0060324498, 0.9977163014]]

# Output, oiiotool arguments, channels, data type, expected pixel hash (a fixture or an output), attributes.
# Every lossless round trip must reproduce its source fixture's pixel hash exactly. 10-bit DPX is RGB: OIIO's
# reader drops the last alpha sample of a 10-bit RGBA row whose sample count leaves one over in its last word.
ROUND_TRIPS = (
    ("half-zip.exr", ["/in/rgba-half.exr", "--compression", "zip"], 4, "half", "rgba-half.exr",
     {"compression": "zip"}),
    ("float-tiled-piz.exr", ["/in/rgba-float.exr", "--tile", "32", "32", "--compression", "piz"], 4, "float",
     "rgba-float.exr", {"compression": "piz", "tile size": "32 x 32"}),
    ("float-to-half.exr", ["/in/rgba-float.exr", "-d", "half"], 4, "half", "rgba-half.exr", {}),
    ("uint8-lzw.tif", ["/in/rgba-uint8.png", "--compression", "lzw"], 4, "uint8", "rgba-uint8.png",
     {"compression": "lzw"}),
    ("uint16-zip.tif", ["/in/rgba-uint16.png", "--compression", "zip"], 4, "uint16", "rgba-uint16.png",
     {"compression": "zip"}),
    ("float-zip.tif", ["/in/rgba-float.exr", "--compression", "zip"], 4, "float", "rgba-float.exr",
     {"compression": "zip"}),
    ("uint8.png", ["/in/rgba-uint8.png"], 4, "uint8", "rgba-uint8.png", {}),
    ("uint16.png", ["/in/rgba-uint16.png"], 4, "uint16", "rgba-uint16.png", {}),
    ("rgba-uint16.dpx", ["/in/rgba-uint16.png"], 4, "uint16", "rgba-uint16.png", {"oiio:BitsPerSample": "16"}),
    ("rgb-uint10.dpx", ["/in/rgba-uint16.png", "--ch", "R,G,B", "-d", "uint10"], 3, "uint10", "rgb-uint10.dpx",
     {"oiio:BitsPerSample": "10"}),
    ("rgb-q90.jpg", ["/in/rgba-uint8.png", "--ch", "R,G,B", "--quality", "90"], 3, "uint8", "rgb-q90.jpg", {}),
)

PYTHON_IO = r"""
import hashlib, json, numpy, OpenImageIO as oiio
result = {}
for path, kind, dtype in (("/in/rgba-uint16.png", oiio.UINT16, "<u2"), ("/in/rgba-float.exr", oiio.FLOAT, "<f4")):
    image = oiio.ImageInput.open(path)
    pixels = image.read_image(kind)
    image.close()
    result[path] = {"shape": list(pixels.shape), "dtype": str(pixels.dtype),
                    "sha1": hashlib.sha1(pixels.astype(dtype).tobytes()).hexdigest().upper()}
output = oiio.ImageOutput.create("/out/python-write.exr")
output.open("/out/python-write.exr", oiio.ImageSpec(pixels.shape[1], pixels.shape[0], pixels.shape[2], oiio.FLOAT))
output.write_image(numpy.ascontiguousarray(pixels))
output.close()
print(json.dumps(result))
"""

ERRORS = r"""
import json, sys, numpy, OpenImageIO as oiio
matrix = numpy.array(json.loads(sys.argv[1]))
def read(path):
    return oiio.ImageBuf(path).get_pixels(oiio.FLOAT).astype(numpy.float64)
source, acescg = read("/in/rgba-float.exr"), read("/out/acescg.exr")
reference8 = read("/in/rgba-uint8.png")[..., :3]
jpeg_error = numpy.abs(read("/out/rgb-q90.jpg") - reference8)
print(json.dumps({
    "acescg_max_error": float(numpy.abs(source[..., :3] @ matrix.T - acescg[..., :3]).max()),
    "acescg_alpha_unchanged": bool((source[..., 3] == acescg[..., 3]).all()),
    "jpeg_mean_error": float(jpeg_error.mean()),
    "jpeg_max_error": float(jpeg_error.max()),
}))
"""

OCIO = r"""
import json, PyOpenColorIO as ocio
config = ocio.Config.CreateFromFile("ocio://default")
display = config.getDefaultDisplay()
print(json.dumps({"builtin": sorted(ocio.BuiltinConfigRegistry()),
                  "default": config.getName(), "display": display, "view": config.getDefaultView(display)}))
"""

SHA256 = r"""
import hashlib, json, os
print(json.dumps({name: hashlib.sha256(open(os.path.join("/out", name), "rb").read()).hexdigest()
                  for name in sorted(os.listdir("/out"))}))
"""


def run(args, check=True):
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if check and process.returncode != 0:
        raise RuntimeError("command failed ({0}): {1}\n{2}".format(process.returncode, " ".join(args), process.stdout))
    return process


def parse_info(text):
    """Split iinfo -a -v --hash output into one dict per subimage."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if SUBIMAGE.match(line)] or [0]
    images = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(lines)
        match = HEADER.search(lines[start])
        image = {"size": (int(match.group(1)), int(match.group(2))), "channels": int(match.group(3)),
                 "format": match.group(4), "file_format": match.group(5)}
        for line in lines[start + 1:end]:
            key, separator, value = line.strip().partition(": ")
            if separator:
                image.setdefault(key, value.strip('"'))
        images.append(image)
    return images


class Smoke:
    def __init__(self, image, platform, fixtures, output):
        self.image = image
        self.platform = platform
        self.fixtures = fixtures
        self.output = output
        self.container = "oiio-smoke-{0}".format(os.getpid())
        self.failures = []
        self.results = {}
        self.measurements = {}

    def __enter__(self):
        # One long-lived container keeps each check to a docker exec. It runs as the calling user, with
        # the fixtures mounted read-only and the output directory writable.
        run(["docker", "run", "--detach", "--rm", "--name", self.container, "--platform", self.platform,
             "--user", "{0}:{1}".format(os.getuid(), os.getgid()), "--network", "none",
             "-v", "{0}:/in:ro".format(self.fixtures), "-v", "{0}:/out".format(self.output), "-w", "/out",
             self.image, "sleep", "infinity"])
        return self

    def __exit__(self, *_exc):
        run(["docker", "rm", "--force", self.container], check=False)

    def exec(self, *args, check=True):
        return run(["docker", "exec", self.container] + list(args), check=check).stdout

    def python(self, script, *args):
        return json.loads(self.exec("python3", "-c", script, *args).strip().splitlines()[-1])

    def info(self, path):
        return parse_info(self.exec("iinfo", "-a", "-v", "--hash", path))

    def expect(self, label, actual, expected):
        ok = actual == expected
        self.results[label] = {"actual": actual, "expected": expected, "ok": ok}
        print("{0} {1}: {2}{3}".format("PASS" if ok else "FAIL", label, actual,
                                       "" if ok else " (expected {0})".format(expected)))
        if not ok:
            self.failures.append(label)

    def expect_image(self, label, image, size, channels, data_type, sha1, attributes=None):
        actual = {"size": list(image["size"]), "channels": image["channels"], "format": image["format"],
                  "SHA-1": image.get("SHA-1")}
        expected = {"size": list(size), "channels": channels, "format": data_type, "SHA-1": sha1}
        for key, value in (attributes or {}).items():
            actual[key] = image.get(key)
            expected[key] = value
        self.expect(label, actual, expected)


def run_checks(smoke, contract, year):
    fixtures = contract["fixtures"]
    size = (fixtures["rgba-uint8.png"]["width"], fixtures["rgba-uint8.png"]["height"])
    expected_hash = {name: item["pixel_sha1"] for name, item in fixtures.items()}
    expected_hash.update(contract["derived_pixel_sha1"])
    expected_hash.update(contract["lossy_pixel_sha1"])

    formats = smoke.exec("python3", "-c", "import OpenImageIO as o; print(o.get_string_attribute('format_list'))")
    smoke.expect("format plugins", sorted(formats.strip().split(",")), sorted(contract["formats"]))
    excluded = smoke.exec("oiiotool", "/in/rgba-uint8.png", "-o", "excluded.tga", check=False)
    smoke.expect("excluded format refused", "could not find a format writer" in excluded.lower()
                 or "unknown file format" in excluded.lower() or "not a supported" in excluded.lower(), True)

    for name, item in sorted(fixtures.items()):
        images = smoke.info("/in/" + name)
        smoke.expect_image("read fixture " + name, images[0], size, item["channels"], item["format"], item["pixel_sha1"])

    for output, arguments, channels, data_type, source, attributes in ROUND_TRIPS:
        smoke.exec("oiiotool", *arguments, "-o", output)
        smoke.expect_image("round trip " + output, smoke.info(output)[0], size, channels, data_type,
                           expected_hash[source], attributes)

    smoke.exec("oiiotool", "/in/rgba-half.exr", "/in/rgba-float.exr", "--siappend", "-o", "multipart.exr")
    parts = smoke.info("multipart.exr")
    smoke.expect("multipart subimages", len(parts), 2)
    for index, source in enumerate(("rgba-half.exr", "rgba-float.exr")):
        if index < len(parts):
            smoke.expect_image("multipart part {0}".format(index), parts[index], size, 4,
                               fixtures[source]["format"], expected_hash[source])

    smoke.exec("maketx", "/in/rgba-float.exr", "-o", "texture.tx")
    texture = smoke.info("texture.tx")[0]
    smoke.expect_image("maketx texture", texture, size, 4, "float", expected_hash["rgba-float.exr"], {
        "MIP-map levels": "67x43 33x21 16x10 8x5 4x2 2x1 1x1", "tile size": "64 x 64",
        "textureformat": "Plain Texture"})
    smoke.expect("maketx file format", texture["file_format"], "tiff")

    year_ocio = contract["ocio"][year]
    ocio = smoke.python(OCIO)
    smoke.expect("OCIO built-in configs", ocio["builtin"], year_ocio["builtin_configs"])
    smoke.expect("OCIO default config", ocio["default"], year_ocio["default_config"])
    smoke.expect("OCIO default display and view", [ocio["display"], ocio["view"]],
                 [year_ocio["display"], year_ocio["view"]])
    smoke.exec("oiiotool", "/in/rgba-float.exr", "--colorconvert", "ACES2065-1", "ACEScg", "-o", "acescg.exr")
    smoke.exec("oiiotool", "/in/rgba-half.exr", "--iscolorspace", "ACES2065-1",
               "--ociodisplay", year_ocio["display"], year_ocio["view"], "-d", "uint8", "-o", "display.png")
    smoke.expect_image("OCIO display transform", smoke.info("display.png")[0], size, 4, "uint8",
                       year_ocio["display_pixel_sha1"][smoke.platform])

    errors = smoke.python(ERRORS, json.dumps(AP0_TO_AP1))
    smoke.measurements.update(errors)
    print("INFO ACEScg max error {acescg_max_error:.3g}; JPEG mean error {jpeg_mean_error:.3g}, "
          "max {jpeg_max_error:.3g}".format(**errors))
    smoke.expect("OCIO ACES2065-1 to ACEScg matches the AP0-to-AP1 matrix",
                 errors["acescg_max_error"] <= 1e-5 and errors["acescg_alpha_unchanged"], True)
    # The JPEG's exact pixels are its frozen hash; this bound only confirms it decodes to the fixture. The
    # fixture's blue channel is deliberately high-frequency, which JPEG's chroma subsampling blurs.
    smoke.expect("JPEG decodes close to the fixture", errors["jpeg_mean_error"] <= 0.1, True)

    python_io = smoke.python(PYTHON_IO)
    for path, name, dtype in (("/in/rgba-uint16.png", "rgba-uint16.png", "uint16"),
                              ("/in/rgba-float.exr", "rgba-float.exr", "float32")):
        smoke.expect("python read " + name, python_io[path],
                     {"shape": [size[1], size[0], 4], "dtype": dtype, "sha1": expected_hash[name]})
    smoke.expect_image("python write EXR", smoke.info("python-write.exr")[0], size, 4, "float",
                       expected_hash["rgba-float.exr"])

    # The host must see every output the container wrote, byte for byte, owned by the calling user.
    inside = smoke.python(SHA256)
    outside, owners = {}, set()
    for name in sorted(os.listdir(smoke.output)):
        path = os.path.join(smoke.output, name)
        with open(path, "rb") as handle:
            outside[name] = hashlib.sha256(handle.read()).hexdigest()
        owners.add(os.stat(path).st_uid)
    smoke.expect("mounted outputs match on the host", outside == inside and len(outside) >= len(ROUND_TRIPS), True)
    smoke.expect("mounted outputs owned by the calling user", sorted(owners), [os.getuid()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", required=True, choices=("linux/amd64", "linux/arm64"))
    parser.add_argument("--year", required=True, help="platform year, for example cy2026")
    parser.add_argument("--contract", default=os.path.join(REPO, "build", "image-support.json"))
    parser.add_argument("--work-dir", help="new directory for fixtures and outputs (default: a temporary one)")
    parser.add_argument("--metadata", help="write results as JSON to this path")
    args = parser.parse_args()

    with open(args.contract) as contract_file:
        contract = json.load(contract_file)
    if args.work_dir:
        os.makedirs(args.work_dir)
        work = os.path.abspath(args.work_dir)
    else:
        work = tempfile.mkdtemp(prefix="oiio-smoke-")
    fixtures, output = os.path.join(work, "fixtures"), os.path.join(work, "out")
    os.mkdir(output)
    generated = generate_fixtures(pathlib.Path(fixtures))
    if generated != contract["fixtures"] or derived_hashes() != contract["derived_pixel_sha1"]:
        print("fixture identity changed: generated {0}, derived {1}".format(
            json.dumps(generated, sort_keys=True), json.dumps(derived_hashes())), file=sys.stderr)
        return 1

    with Smoke(args.image, args.platform, fixtures, output) as smoke:
        try:
            run_checks(smoke, contract, args.year)
        except (KeyError, RuntimeError, ValueError, AttributeError) as error:
            smoke.failures.append("error: {0}".format(error))
            print("FAIL {0}".format(error))

    if args.metadata:
        with open(args.metadata, "w") as metadata:
            json.dump({"image": args.image, "platform": args.platform, "year": args.year, "work_dir": work,
                       "failures": smoke.failures, "results": smoke.results, "measurements": smoke.measurements},
                      metadata, indent=2, sort_keys=True)
    print("{0} ({1}, {2}): {3} check(s), {4} failure(s); outputs in {5}".format(
        args.image, args.year, args.platform, len(smoke.results), len(smoke.failures), output))
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    sys.exit(main())
