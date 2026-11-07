#!/usr/bin/env python3
"""Generate deterministic PNG and OpenEXR fixtures for the image support checks, without OIIO."""

import argparse
import binascii
import hashlib
import json
import pathlib
import struct
import zlib

# Odd, non-square dimensions catch transposed axes, padding, and tile-edge mistakes.
WIDTH = 67
HEIGHT = 43
CHANNELS = ("R", "G", "B", "A")


def pixel(x, y):
    """Return linear RGBA floats for one pixel: ramps, a repeating pattern, and highlights above 1.0."""
    red = x / (WIDTH - 1)
    green = y / (HEIGHT - 1)
    blue = ((x * 7 + y * 13) % 17) / 16
    # Every alpha value is 0 or 1, so premultiplying on read and unpremultiplying on write are exact.
    alpha = 0.0 if (x // 8 + y // 8) % 5 == 0 else 1.0
    return red, green, blue, alpha


def scaled(value, maximum):
    return int(round(min(max(value, 0.0), 1.0) * maximum))


def integer_pixels(maximum):
    """Rows of interleaved integer RGBA values; colour is zero wherever alpha is zero."""
    rows = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            red, green, blue, alpha = pixel(x, y)
            row.extend(scaled(value * alpha, maximum) for value in (red, green, blue))
            row.append(scaled(alpha, maximum))
        rows.append(row)
    return rows


def float_pixels():
    """Rows of interleaved float RGBA values, with associated alpha and HDR values up to 4.0."""
    rows = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            red, green, blue, alpha = pixel(x, y)
            row.extend((red * 4.0 * alpha, green * alpha, blue * 2.0 * alpha, alpha))
        rows.append(row)
    return rows


def png_chunk(kind, data):
    content = kind + data
    return struct.pack(">I", len(data)) + content + struct.pack(">I", binascii.crc32(content) & 0xffffffff)


def write_png(path, rows, bits):
    sample = ">B" if bits == 8 else ">H"
    raw = b"".join(b"\0" + b"".join(struct.pack(sample, value) for value in row) for row in rows)
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, bits, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
    data += png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b"")
    path.write_bytes(data)


def exr_attribute(name, kind, value):
    return name.encode("ascii") + b"\0" + kind.encode("ascii") + b"\0" + struct.pack("<i", len(value)) + value


def write_exr(path, rows, pixel_type):
    """Write an uncompressed, single-part scanline OpenEXR file; pixel_type is 1 (half) or 2 (float)."""
    sample = "<e" if pixel_type == 1 else "<f"
    order = sorted(range(len(CHANNELS)), key=lambda index: CHANNELS[index])
    channel_list = b"".join(CHANNELS[index].encode("ascii") + b"\0" + struct.pack("<iB3xii", pixel_type, 0, 1, 1)
                            for index in order) + b"\0"
    window = struct.pack("<iiii", 0, 0, WIDTH - 1, HEIGHT - 1)
    header = b"\x76\x2f\x31\x01" + struct.pack("<i", 2)
    header += exr_attribute("channels", "chlist", channel_list)
    header += exr_attribute("compression", "compression", b"\0")
    header += exr_attribute("dataWindow", "box2i", window)
    header += exr_attribute("displayWindow", "box2i", window)
    header += exr_attribute("lineOrder", "lineOrder", b"\0")
    header += exr_attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    header += exr_attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
    header += exr_attribute("screenWindowWidth", "float", struct.pack("<f", 1.0)) + b"\0"
    chunks = []
    for y, row in enumerate(rows):
        # Each scanline stores its channels one after another, in channel-name order.
        data = b"".join(struct.pack(sample, row[x * len(CHANNELS) + index]) for index in order for x in range(WIDTH))
        chunks.append(struct.pack("<ii", y, len(data)) + data)
    offset = len(header) + 8 * len(chunks)
    table = b""
    for chunk in chunks:
        table += struct.pack("<Q", offset)
        offset += len(chunk)
    path.write_bytes(header + table + b"".join(chunks))


def pixel_hash(rows, sample):
    """The SHA-1 that iinfo --hash reports: interleaved pixels in the file's data type, little-endian."""
    return hashlib.sha1(b"".join(struct.pack(sample, value) for row in rows for value in row)).hexdigest().upper()


def truncated_10bit(value):
    """OIIO writes a 16-bit sample to 10-bit DPX by truncation and reads it back with its top bits replicated."""
    code = value >> 6
    return (code << 6) | (code >> 4)


def derived_hashes():
    """Pixel hashes of outputs whose exact pixels follow from the fixtures."""
    rgb10 = [[truncated_10bit(value) for index, value in enumerate(row) if index % 4 != 3]
             for row in integer_pixels(65535)]
    return {"rgb-uint10.dpx": pixel_hash(rgb10, "<H")}


FIXTURES = (
    # file name, data type as OIIO reports it
    ("rgba-uint8.png", "uint8"),
    ("rgba-uint16.png", "uint16"),
    ("rgba-half.exr", "half"),
    ("rgba-float.exr", "float"),
)


def generate(directory):
    """Write the fixtures to directory and return their identities."""
    directory.mkdir(parents=True, exist_ok=True)
    rows8, rows16, rowsf = integer_pixels(255), integer_pixels(65535), float_pixels()
    write_png(directory / "rgba-uint8.png", rows8, 8)
    write_png(directory / "rgba-uint16.png", rows16, 16)
    write_exr(directory / "rgba-half.exr", rowsf, 1)
    write_exr(directory / "rgba-float.exr", rowsf, 2)
    hashes = {
        "rgba-uint8.png": pixel_hash(rows8, "<B"),
        "rgba-uint16.png": pixel_hash(rows16, "<H"),
        "rgba-half.exr": pixel_hash(rowsf, "<e"),
        "rgba-float.exr": pixel_hash(rowsf, "<f"),
    }
    fixtures = {}
    for name, data_type in FIXTURES:
        fixtures[name] = {
            "width": WIDTH,
            "height": HEIGHT,
            "channels": len(CHANNELS),
            "format": data_type,
            "pixel_sha1": hashes[name],
            "file_sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
        }
    return fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.directory), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
