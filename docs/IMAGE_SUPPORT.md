# Image Support Contract

This document lists what every image supports and how each capability is checked. `build/image-support.json` holds the contract in machine-readable form: the enabled and excluded OIIO format plugins, the fixture identities, the expected pixel hashes, and each year's OCIO configuration. `scripts/smoke_images.py` runs the checks against a built image, and `scripts/validate_lock.py` checks the contract against the Dockerfile and the fixture generator without building.

The contract is the same for every year and architecture except for the OCIO configurations, which follow each year's OCIO release.

## Capability Matrix

| Capability | Checked by `smoke_images.py` | Provided by |
| --- | --- | --- |
| OpenEXR | Reads half and float scanline files; writes and rereads half scanline (ZIP), float tiled 32×32 (PIZ), float converted to half, and a two-part multipart file | OIIO `openexr` plugin, OpenEXR, Imath |
| TIFF | Writes and rereads 8-bit (LZW), 16-bit (ZIP), and float (ZIP) RGBA | OIIO `tiff` plugin, libtiff, zlib |
| PNG | Reads and rewrites 8-bit and 16-bit RGBA | OIIO `png` plugin, libpng, zlib |
| JPEG | Writes and rereads 8-bit RGB at quality 90 | OIIO `jpeg` plugin, libjpeg-turbo |
| DPX | Writes and rereads 16-bit RGBA and 10-bit RGB | OIIO `dpx` plugin, with OIIO's own DPX library |
| Textures | `maketx` from a float EXR: a float TIFF with seven MIP levels and 64×64 tiles | OIIO `maketx`, the `tiff` plugin |
| Colour | Each year's built-in OCIO configs, default config, default display and view; an ACES2065-1 to ACEScg conversion; a display transform | OCIO and its built-in configs |
| Python | `ImageInput` reads of a 16-bit PNG and a float EXR into NumPy arrays, and an `ImageOutput` write of a NumPy array | CPython, NumPy, the `OpenImageIO` module |
| Mounted files | Fixtures mounted read-only; every output written to a writable mount, then compared on the host | Docker bind mounts |
| Excluded formats | OIIO's format list is exactly the five formats above, and writing a `.tga` file fails | OIIO configure options in the Dockerfile |

Rocky Linux supplies only glibc, `libstdc++`, and `libgcc_s` to these libraries. Every format library is built from a locked source ([SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md)):

| Library | CY2025 | CY2026 | CY2027 |
| --- | --- | --- | --- |
| OpenEXR | 3.3.15 | 3.4.17 | 3.5.3 |
| libtiff | 4.7.1 | 4.7.1 | 4.7.1 |
| libpng | 1.6.50 | 1.6.50 | 1.6.58 |
| libjpeg-turbo | 3.1.2 | 3.1.2 | 3.1.2 |
| zlib | 1.3.1 | 1.3.1 | 1.3.2 |
| OIIO (DPX) | 3.1.19.0 | 3.1.19.0 | 3.2.2.0 |

libtiff is built with zlib and JPEG compression only; LZMA, Zstandard, WebP, JBIG, LERC, and libdeflate are off. OpenEXR builds its own compression codecs.

## How Pixels Are Checked

`scripts/generate_test_images.py` writes four 67×43 RGBA fixtures with the Python standard library alone: 8-bit and 16-bit PNG, and half and float uncompressed scanline OpenEXR. It does not use OIIO, so each fixture's pixel hash is computed independently of the image under test. The odd, non-square size catches swapped axes and partial tiles. Alpha is 0 or 1, and colour is zero wherever alpha is zero, so associating and unassociating alpha are exact. The float fixtures hold values up to 4.0.

The pixel hash is what `iinfo --hash` reports: the SHA-1 of the decoded pixels in the file's own data type, interleaved, little-endian. The checks compare it in three ways:

- **Lossless round trips** must reproduce their source fixture's hash exactly. Converting the float fixture to half must give the half fixture's hash, because the generator rounds to half the same way OpenEXR does.
- **10-bit DPX** has a hash the generator derives: OIIO truncates each 16-bit sample to 10 bits and reads it back with the top bits replicated.
- **Lossy outputs** have frozen hashes: the quality-90 JPEG. The same hash was produced by every year and architecture. A loose error bound also confirms that the JPEG decodes to the fixture.

The ACES2065-1 to ACEScg conversion is compared with the published AP0-to-AP1 matrix, within 1e-5; the measured error is under 1e-6. The display transform's hash is recorded per year and architecture, because OCIO's SIMD code paths differ between amd64 and arm64 by one 8-bit code value in one or two pixels.

Every check also compares width, height, channel count, and data type, and the relevant file attributes: compression, tile size, bits per sample, and MIP levels.

## Colour Management

Each image provides the built-in configs of its OCIO release. `ocio://default` selects the newest CG config.

| Year | OCIO | Default config | ACES | Default display and view | Built-in configs |
| --- | --- | --- | --- | --- | --- |
| CY2025 | 2.4 | `cg-config-v2.2.0_aces-v1.3_ocio-v2.4` | 1.3 | sRGB - Display, ACES 1.0 - SDR Video | CG and studio configs v1.0.0, v2.1.0, and v2.2.0 (ACES 1.3) |
| CY2026 | 2.5 | `cg-config-v4.0.0_aces-v2.0_ocio-v2.5` | 2.0 | sRGB - Display, ACES 2.0 - SDR 100 nits (Rec.709) | Those, plus v4.0.0 (ACES 2.0) |
| CY2027 | 2.6 | `cg-config-v5.0.0_aces-v2.1_ocio-v2.6` | 2.1 | sRGB - Display, ACES 2.0 - SDR 100 nits (Rec.709) | Those, plus v5.0.0 (ACES 2.1) |

[PLATFORMS.md](PLATFORMS.md) records where these ACES versions differ from the VFX Reference Platform. To use a facility config instead, mount it and set `OCIO`, for example `-v /path/to/config:/ocio:ro -e OCIO=/ocio/config.ocio`.

## Mounted Files

Images enter and leave the container through bind mounts. The image's default user, `algernon`, has UID 1000. To write into a host directory, run as your own user, which is what `smoke_images.py` does:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -w /work algernon_vfx/oiio:cy2026 \
  oiiotool input.exr --colorconvert ACES2065-1 ACEScg -o output.exr
```

The smoke check runs with `--network none`, mounts the fixtures read-only, and confirms that the host sees every output byte for byte, owned by the calling user.

## Excluded Formats

These OIIO format plugins are disabled in every year. `validate_lock.py` checks that the contract accounts for every plugin in OIIO 3.1 and 3.2, and that the Dockerfile disables each excluded one.

- **Built into OIIO, disabled by this project:** BMP, Cineon, DDS, FITS, HDR (Radiance RGBE), ICO, IFF, PNM, PSD, RLA, SGI, Softimage PIC, Targa, the terminal writer (`term`), Zfile, and the `null` pseudo-format.
- **Needing a library these images do not build:** DICOM, FFmpeg (movie files), GIF, HEIF and AVIF, JPEG 2000 (OpenJPEG and OpenJPH), JPEG XL, OpenVDB, Ptex, camera RAW, RED R3D, and WebP. The JPEG plugin is built without Ultra HDR gain-map support (libuhdr).

Opening or writing an excluded format fails, for example `oiiotool ERROR: -o : OpenImageIO could not find a format writer for "out.tga"`.

To add a format: move it from `excluded_formats` to `formats` in `build/image-support.json`, remove its `-D…=OFF` option from the Dockerfile (and lock any library it needs), add a round trip to `smoke_images.py`, rebuild every year on both architectures, and update this document.

## Known Limitations

- **10-bit RGBA DPX:** OIIO's DPX reader drops the last alpha sample of a 10-bit RGBA row when the row's sample count leaves one sample in its last 32-bit word, which happens when the width is one more than a multiple of three (1024 and 4096 among them). The file itself is correct: the writer stores the sample, and a 67-pixel-wide file's raw bytes contain it. Reproduced with OIIO 3.1.19.0 and 3.2.2.0. 10-bit RGB and single-channel files are not affected. The contract therefore checks 10-bit DPX as RGB. OIIO's fix for a related single-channel case ([#5298](https://github.com/AcademySoftwareFoundation/OpenImageIO/pull/5298)) does not cover it, and no upstream report was found on 2026-11-07.
- **16-bit to 10-bit conversion truncates:** writing a 16-bit image to 10-bit DPX truncates each sample instead of rounding, so values can come out up to one 10-bit code low.
- **Not checked:** other OpenEXR compressions (RLE, ZIPS, PXR24, B44, B44A, DWAA, DWAB, and HTJ2K), deep OpenEXR, TIFF JPEG compression, 12-bit DPX, CMYK and grayscale files, and OCIO GPU processing. They may work, but the contract makes no claim for them.

## Running The Checks

```sh
python3 scripts/smoke_images.py --image algernon_vfx/oiio:cy2026 --platform linux/arm64 --year cy2026
```

The script generates the fixtures in a new temporary directory, or in a new directory given with `--work-dir`, and stops if their identities differ from the contract. It runs every check in one container, prints `PASS` or `FAIL` for each, and exits non-zero on any failure. `--metadata` writes the results as JSON.

`scripts/validate_image.py` remains the image's identity, linkage, and size check; run both.
