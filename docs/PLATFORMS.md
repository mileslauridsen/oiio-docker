# Platforms

This page is the support contract for the `algernon_vfx/oiio` images. Each image matches one [VFX Reference Platform](https://vfxplatform.com/#reference-platform) calendar year. It lists only what has been built and checked. The evidence for each result is in the [implementation log](IMPLEMENTATION.md).

## Choosing An Image

Pick the year your DCCs and plugins target. A plugin or tool built for a platform year expects that year's compiler, glibc, Python, and library series, so mixing years can fail at load time.

| Image | Platform year | Status | Base (glibc) | Lock |
| --- | --- | --- | --- | --- |
| `algernon_vfx/oiio:cy2025` | CY2025 | supported | Rocky Linux 8.10 (2.28) | [cy2025.json](../build/locks/cy2025.json) |
| `algernon_vfx/oiio:cy2026` and `latest` | CY2026 | current | Rocky Linux 8.10 (2.28) | [cy2026.json](../build/locks/cy2026.json) |
| `algernon_vfx/oiio:cy2027` | CY2027 | Final, effective 2027-01-01 | Rocky Linux 9.8 (2.34) | [cy2027.json](../build/locks/cy2027.json) |

There is no CY2024 image. See [CY2024](#cy2024-not-built).

Build one year for one architecture with the bake file, then run it:

```sh
docker buildx bake --set '*.platform=linux/arm64' --load cy2025
docker run -it --rm -v "$PWD:/work" -w /work --entrypoint bash algernon_vfx/oiio:cy2025
```

Use `linux/amd64` for x86-64. Every image runs as the non-root user `algernon`, with everything installed under `/opt/vfx` and on `PATH`.

## What Every Image Contains

- OIIO's command-line tools, including `oiiotool`, `iinfo`, and `maketx`.
- Python with NumPy and the `OpenImageIO` and `PyOpenColorIO` modules.
- The libraries those need: OCIO, OpenEXR, Imath, libtiff, libpng, libjpeg-turbo, and zlib, all built from locked, checksum-verified sources.

Each image was checked on `linux/amd64` and `linux/arm64` with `scripts/validate_image.py`, which passed all 35 of its checks. The checks cover:

- tool, library, and Python versions against the lock;
- glibc and `libstdc++` symbol versions against the base OS;
- unresolved libraries and excluded components;
- EXR, TIFF, PNG, and JPEG round trips, `maketx`, a NumPy read, and NumPy linear algebra;
- an OCIO ACES2065-1 to ACEScg conversion;
- the size budget.

Other image formats that OIIO builds in without extra libraries may also work, but they are not checked.

## Components Left Out

These platform components are not shipped, and the images make no compliance claim for them: Qt, PyQt, PySide, Boost, oneTBB, oneMKL, Alembic, FBX, OpenSubdiv, OpenVDB, and Ptex.

OIIO is built without these optional plugins and features: FFmpeg, GIF, HEIF, RAW, OpenJPEG, OpenJPH, WebP, JPEG XL, Ultra HDR, DICOM, Ptex, OpenVDB, OpenCV, FreeType, Qt (`iv`), OpenGL, and the Nuke plugins. OCIO is built without its command-line apps, GPU tests, and OpenFX plugins.

## CY2025

| Component | Specified | Verified |
| --- | --- | --- |
| glibc | 2.28 | 2.28 |
| gcc | 11.2.1 | 11.2.1 (`gcc-toolset-11`) |
| C++ standard | C++17 | C++17 |
| Python | 3.11 | 3.11.18 |
| NumPy | 1.26 | 1.26.4 |
| OpenColorIO | 2.4 | 2.4.2 |
| OpenEXR | 3.3 | 3.3.15 |
| Imath | 3.1 | 3.1.12 |
| ACES | 2.0 | 1.3 built-in configs; see deviations |
| OpenImageIO | not specified | 3.1.19.0 |

Deviations:

- **ACES:** OCIO 2.4's built-in configs are all ACES 1.3; the default is `cg-config-v2.2.0_aces-v1.3_ocio-v2.4`. OCIO 2.4 does include the ACES 2.0 output transforms, so an ACES 2.0 config written for OCIO 2.4 can use them. Supply one through the `OCIO` environment variable, for example `docker run -e OCIO=/work/config.ocio ...`. No external ACES 2.0 config has been tested in this image.
- **Helper libraries:** OCIO 2.4 recommends older releases. The image uses the same security-patched releases as CY2026 (expat 2.7.2, yaml-cpp 0.8.0, zlib 1.3.1, and minizip-ng 4.0.10), which meet OCIO 2.4's minimums.
- **OIIO:** 3.1.19.0, the same release as CY2026. ASWF's CY2025 reference pin, 3.1.6.2, is in the same series.

Highest symbol versions required: `GLIBC_2.28` and `GLIBCXX_3.4.22`. Rocky 8's `libstdc++` provides up to `GLIBCXX_3.4.25`.

## CY2026

| Component | Specified | Verified |
| --- | --- | --- |
| glibc | 2.28 | 2.28 |
| gcc | 14.2.1 | 14.2.1 (`gcc-toolset-14`) |
| C++ standard | C++20 | C++20 |
| Python | 3.13 | 3.13.18 |
| NumPy | 2.3 | 2.3.5 |
| OpenColorIO | 2.5 | 2.5.2 |
| OpenEXR | 3.4 | 3.4.17 |
| Imath | 3.2 | 3.2.3 |
| ACES | 2.0 | 2.0, the default built-in config `cg-config-v4.0.0_aces-v2.0_ocio-v2.5` |
| OpenImageIO | not specified | 3.1.19.0 |

Deviations:

- **OIIO:** 3.1.19.0, the newest 3.1 patch, in place of ASWF's reference pin 3.1.18.1.

Highest symbol versions required: `GLIBC_2.28` and `GLIBCXX_3.4.22`. Rocky 8's `libstdc++` provides up to `GLIBCXX_3.4.25`.

## CY2027

| Component | Specified | Verified |
| --- | --- | --- |
| glibc | 2.34 | 2.34 |
| gcc | 14.2.1 | 14.2.1 (`gcc-toolset-14`) |
| C++ standard | C++20 | C++20 |
| Python | 3.13 | 3.13.18 |
| NumPy | 2.4 | 2.4.6 |
| OpenColorIO | 2.6 | 2.6.0 |
| OpenEXR | 3.5 | 3.5.3 |
| Imath | 3.2 | 3.2.3 |
| ACES | 2.0 | 2.0 built-in configs; the default is ACES 2.1 |
| OpenImageIO | not specified | 3.2.2.0 |

Deviations:

- **ACES:** OCIO 2.6's default built-in config is `cg-config-v5.0.0_aces-v2.1_ocio-v2.6` (ACES 2.1). The ACES 2.0 configs that CY2027 specifies are still built in. To use one, set `OCIO=ocio://cg-config-v4.0.0_aces-v2.0_ocio-v2.5` or `OCIO=ocio://studio-config-v4.0.0_aces-v2.0_ocio-v2.5`. Both were checked on arm64: OCIO loads them, and an ACES2065-1 to ACEScg conversion works in PyOpenColorIO and in OIIO.
- **OIIO:** 3.2.2.0 in place of ASWF's reference pin 3.2.1.1. OIIO 3.2 builds its Python bindings with nanobind, its new default, instead of pybind11. OCIO still uses pybind11.
- **CPU baseline:** OIIO 3.2's amd64 build defaults to SSE4.2 (x86-64-v2). Rocky Linux 9 already requires x86-64-v2 hardware, so this adds no new requirement.

Highest symbol versions required: `GLIBC_2.34` and `GLIBCXX_3.4.29`. `GLIBCXX_3.4.29` is the most Rocky 9's `libstdc++` provides, so CY2027 has no headroom on that check.

## CY2024 (Not Built)

CY2024 is still in the platform's support window, but there is no image for it:

- CY2024's OIIO series, 2.5, requires Boost, which these images leave out.
- Moving CY2024 to OIIO 3 would remove Boost, but the image would no longer provide the OIIO 2.5 interface that CY2024 software builds against.
- CY2024 is the first of the supported years to leave the window, on 2028-01-01.

## All Years

- **CPU baseline:** amd64 code compiles for generic x86-64. OIIO's SIMD is SSE2 for CY2025 and CY2026, and SSE4.2 for CY2027. arm64 code compiles for ARMv8-A, and OIIO uses NEON.
- **OCIO on arm64:** the CY2026 and CY2027 builds were found not to enable OCIO's NEON SIMD path, so OCIO runs its scalar code there. CY2025 uses the same build options.
- **Python packages:** only NumPy is installed. The image has no `pip`.

## Verified Images

Sizes are uncompressed, from `docker image inspect` after a container has run. The image IDs are from local builds, tagged `cy<year>-<arch>` for testing; the images are not published to a registry, so there are no registry digests. Building with the bake file's own tags or the plain `docker build` gives images with the same layers and config but a different local image ID. The size budgets are in [build/image-size-budgets.json](../build/image-size-budgets.json).

| Image | Platform | Image ID | Size |
| --- | --- | --- | --- |
| cy2025 | linux/amd64 | `sha256:19fb8c182f7b2eb2ba40818e2d4469de21bb9dfcb8e8e95d066e968b4bd9af58` | 361 MB |
| cy2025 | linux/arm64 | `sha256:2310be2c93c88cbaf21dc5b0f115c4727a7c9e6fa142ee897ab1be25c2c3668a` | 345 MB |
| cy2026 | linux/amd64 | `sha256:b91701f9e6f2431ef91f7e6422db14d6691a22198a03967d30431cc9a4effe75` | 332 MB |
| cy2026 | linux/arm64 | `sha256:63d014790cc84283a2b260521abab3fd52449b91919a108a9f08b33bbd6b8a35` | 335 MB |
| cy2027 | linux/amd64 | `sha256:c4f9d81ef5cdef07c08c2a1b7173cbd880d3040a2cff5e3bdd5c2f3d1d737fa8` | 423 MB |
| cy2027 | linux/arm64 | `sha256:2ecc113fb1a0120a4b70210c0982e24d2afbb59e28a6f6532d87f5717f4126fa` | 437 MB |

The amd64 images were built and checked under emulation on an arm64 host. They have not yet been run on x86-64 hardware.

CY2027 is about 90–100 MB larger than CY2026 because of its base: Rocky Linux 9.8 minimal is 242 MB, against 147 MB for Rocky 8.10 minimal. `/opt/vfx` is 140–146 MB in every year (arm64, measured with `du`).

## Annual Maintenance

- **Add a year when it becomes Final,** usually late summer: add `build/locks/cy<year>.json`, a bake target, and size budgets; build both architectures; pass the validator; and add the year to this page.
- **Move `latest` on January 1** to the new current year, in `docker-bake.hcl` and in the Dockerfile's default build arguments, so the plain `docker build` follows it. On 2027-01-01, `latest` moves from CY2026 to CY2027.
- **Drop the oldest year when it leaves the window.** The platform supports the current year and the three before it, so CY2025 leaves on 2029-01-01.
- **Refresh inputs deliberately:** base-image digests, Rocky packages, and security patch releases. Change the lock, rebuild every year that shares the change, rerun the validator, and record the new image IDs and sizes here and in the implementation log.

Last updated: 2026-11-02
