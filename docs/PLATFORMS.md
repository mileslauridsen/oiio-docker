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
- Reading and writing OpenEXR, TIFF, PNG, JPEG, and DPX. [IMAGE_SUPPORT.md](IMAGE_SUPPORT.md) is the support contract.

Each image was checked on `linux/amd64` and `linux/arm64` with `scripts/validate_image.py`, which passed all 48 of its checks. The checks cover:

- tool, library, and Python versions against the lock;
- glibc and `libstdc++` symbol versions against the base OS;
- the runtime image's RPM set against its lock;
- unresolved libraries and excluded components;
- the contents: no compilers, build tools, build-stage directories, headers, static archives, or build configs outside NumPy's wheel; stripped binaries outside NumPy; Bash and the `algernon` user;
- the license and notice files of every shipped component, against the lock and their recorded hashes ([SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md#shipped-licenses));
- EXR, TIFF, PNG, and JPEG round trips, `maketx`, a NumPy read, and NumPy linear algebra;
- an OCIO ACES2065-1 to ACEScg conversion;
- the unpacked size against its budget.

Each image also passed all of `scripts/smoke_images.py`'s checks of the [image support contract](IMAGE_SUPPORT.md): format round trips against fixed pixel hashes, `maketx`, OCIO conversions, Python I/O, and mounted output. OIIO's other formats are disabled.

## Components Left Out

These platform components are not shipped, and the images make no compliance claim for them: Qt, PyQt, PySide, Boost, oneTBB, oneMKL, Alembic, FBX, OpenSubdiv, OpenVDB, and Ptex.

OIIO is built without these optional plugins and features: FFmpeg, GIF, HEIF, RAW, OpenJPEG, OpenJPH, WebP, JPEG XL, Ultra HDR, DICOM, Ptex, OpenVDB, OpenCV, FreeType, Qt (`iv`), OpenGL, and the Nuke plugins. Its built-in readers and writers for formats outside the support contract are disabled too; [IMAGE_SUPPORT.md](IMAGE_SUPPORT.md#excluded-formats) lists them. OCIO is built without its command-line apps, GPU tests, and OpenFX plugins.

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
- **CPU baseline:** amd64 code compiles for x86-64-v2, so OIIO uses SSE4.2. Rocky Linux 9 already requires x86-64-v2 hardware, so this adds no new requirement.

Highest symbol versions required: `GLIBC_2.34` and `GLIBCXX_3.4.29`. `GLIBCXX_3.4.29` is the most Rocky 9's `libstdc++` provides, so CY2027 has no headroom on that check.

## CY2024 (Not Built)

CY2024 is still in the platform's support window, but there is no image for it:

- CY2024's OIIO series, 2.5, requires Boost, which these images leave out.
- Moving CY2024 to OIIO 3 would remove Boost, but the image would no longer provide the OIIO 2.5 interface that CY2024 software builds against.
- CY2024 is the first of the supported years to leave the window, on 2028-01-01.

## All Years

- **CPU baseline:** amd64 code compiles for generic x86-64 (x86-64-v1) in CY2025 and CY2026, and for x86-64-v2 in CY2027. OIIO's SIMD follows that baseline: SSE2 for CY2025 and CY2026, SSE4.2 for CY2027. arm64 code compiles for ARMv8-A, and OIIO uses NEON. See [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md#cpu-baselines).
- **OCIO on arm64:** the CY2026 and CY2027 builds were found not to enable OCIO's NEON SIMD path, so OCIO runs its scalar code there. CY2025 uses the same build options.
- **Python packages:** only NumPy is installed. The image has no `pip`.

## Verified Images

The unpacked size is the disk space the image takes once pulled: the sum of its layer sizes, from `docker history --human=false`. The validator checks it against the budgets in [build/image-size-budgets.json](../build/image-size-budgets.json). The compressed size, from `docker save` with Docker Desktop's containerd image store, is close to the download size.

`docker image inspect` reports a larger `.Size` on Docker Desktop, because its containerd image store adds the compressed layers to the unpacked ones. Use the figures here, not that one.

The image IDs are from local cold builds made on 2026-11-07 with the pinned BuildKit builder and the reproducible build settings, tagged for testing; the images are not published to a registry, so there are no registry digests. Each was built twice from separate copies of the repository and gave the same image ID both times, with a creation time of 1970-01-01 (see [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md#reproducible-builds)). Building with the bake file's own tags or the plain `docker build` gives images with the same layers and config but a different local image ID.

| Image | Platform | Image ID | Unpacked | Compressed |
| --- | --- | --- | --- | --- |
| cy2025 | linux/amd64 | `sha256:81427a6797d0faf87287098f96ae51431ef3b6a35b7c4a445f49ae35bea10671` | 272 MB | 88 MB |
| cy2025 | linux/arm64 | `sha256:6632f17cee677f0abe4de942528908fbe8c592552c42a975b073a31d09523e6b` | 262 MB | 82 MB |
| cy2026 | linux/amd64 | `sha256:ddb5b9a64973f1de07d657be43720fc10c6a0756fd138058d34e7d16300b9268` | 247 MB | 84 MB |
| cy2026 | linux/arm64 | `sha256:6c6d6a14d4adeb09d47002328c0cdbd08b0bbff54324b1bfcfbd54259bd7a625` | 255 MB | 79 MB |
| cy2027 | linux/amd64 | `sha256:6c1d831d891b93fe414c6224d281db0b0d866f95e563f1f2ade94326c1abed97` | 316 MB | 106 MB |
| cy2027 | linux/arm64 | `sha256:1222b0caf4e0d84da8000fcb4cfa4255728f8dfba8491cd77dc72f7aaba2f019` | 333 MB | 103 MB |

The amd64 images were built and checked under emulation on an arm64 host. They have not yet been run on x86-64 hardware.

Each image is its Rocky Linux minimal base plus `/opt/vfx`. Unpacked, the Rocky 8.10 minimal base is 104 MB on amd64 and 110 MB on arm64, and the Rocky 9.8 minimal base is 173 MB and 182 MB. That base accounts for almost all of the difference between CY2027 and CY2026. `/opt/vfx` is 140–146 MB in every year (arm64, measured with `du`).

## Annual Maintenance

- **Add a year when it becomes Final,** usually late summer: add `build/locks/cy<year>.json`, a bake target, and size budgets; build both architectures; pass the validator; and add the year to this page.
- **Move `latest` on January 1** to the new current year, in `docker-bake.hcl` and in the Dockerfile's default build arguments, so the plain `docker build` follows it. On 2027-01-01, `latest` moves from CY2026 to CY2027.
- **Drop the oldest year when it leaves the window.** The platform supports the current year and the three before it, so CY2025 leaves on 2029-01-01.
- **Refresh inputs deliberately:** base-image digests, Rocky packages, and security patch releases. Change the lock, rebuild every year that shares the change, rerun the validator, and record the new image IDs and sizes here and in the implementation log.

Last updated: 2026-11-07
