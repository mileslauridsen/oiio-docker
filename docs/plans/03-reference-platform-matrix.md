# Plan: Reference Platform Build Matrix

## Goal

Build and verify one small OIIO and OCIO image for each [VFX Reference Platform](https://vfxplatform.com/#reference-platform) calendar year in the platform's support window. Each image is built from a clean Rocky Linux base. The compiler, glibc, C++ standard, Python, and color and image libraries in each image match that year's specification, so that a studio can pick the image for the platform year its DCCs and plugins target.

## Current State

- The only recipe targets CY2021 (`aswf/ci-vfxall:2021-clang10.5` with a `centos:centos7` runtime). It clones OIIO from a moving branch. CY2021 is outside the platform's support window.
- vfxplatform.com was read on 2026-11-01 (page last modified 2026-10-17). It lists CY2024–CY2027.
  - CY2027 is Final and takes effect on 2027-01-01, so CY2026 is the current year until then.
  - Support guidance: libraries should support "the current calendar year and the three preceding years".
- Rocky Linux package availability was inspected on 2026-11-01 with `linux/arm64` containers (`rockylinux/rockylinux:8` at `sha256:e8a49c5403b687db05d4d67333fa45808fbe74f36e683cec7abb1f7d0f2338c6` and `rockylinux/rockylinux:9` at `sha256:8101994123cf3d0a8fee517bee7f39e555c7d92bd2d9eb3303cc988a0eeed00f`). The amd64 repositories have not been checked yet. The results:
  - Rocky Linux 8.10 has glibc 2.28, `gcc-toolset-11` 11.2.1, and `gcc-toolset-14` 14.2.1. It packages Python 3.11.13 and 3.12, with NumPy 1.23.5 and 1.24.4.
  - Rocky Linux 9.8 has glibc 2.34 and `gcc-toolset-14` 14.2.1. It packages Python 3.11.13, 3.12, and 3.14, with NumPy 1.23.5, 1.24.4, and 2.3.4.
  - Neither release packages Python 3.13. None of the packaged NumPy versions match any year's specified NumPy.
- The development host is an Apple M5 Pro running Docker 29.9.2 with a `linux/arm64` engine. Rocky Linux publishes both `amd64` and `arm64` images.
- Phase 2 has not yet established a build or validation baseline.

## Target Matrix

The specified versions come from vfxplatform.com. The "source" row says where each image gets its components:

- **Rocky**: a Rocky Linux package.
- **src**: a pinned upstream source release.
- **pip**: a pinned wheel.

| | CY2024 | CY2025 | CY2026 | CY2027 |
| --- | --- | --- | --- | --- |
| Platform status | supported | supported | current | Final, effective 2027-01-01 |
| Base OS (glibc floor) | Rocky Linux 8 (2.28) | Rocky Linux 8 (2.28) | Rocky Linux 8 (2.28) | Rocky Linux 9 (2.34) |
| gcc (Rocky `gcc-toolset`) | 11.2.1 (`-11`) | 11.2.1 (`-11`) | 14.2.1 (`-14`) | 14.2.1 (`-14`) |
| C++ standard | C++17 | C++17 | C++20 | C++20 |
| Python (src) | 3.11.x | 3.11.x | 3.13.x | 3.13.x |
| NumPy (pip) | 1.24.x | 1.26.x | 2.3.x | 2.4.x |
| OpenColorIO (src) | 2.3.x | 2.4.x | 2.5.x | 2.6.x |
| OpenEXR (src) | 3.2.x | 3.3.x | 3.4.x | 3.5.x |
| Imath (src) | 3.1.x | 3.1.x | 3.2.x | 3.2.x |
| ACES (platform) | 1.3 | 2.0 | 2.0 | 2.0 |
| OpenImageIO (src, starting pin) | 2.5.19.1 | 3.1.6.2 | 3.1.18.1 | 3.2.1.1 |

Step 1 chooses the exact patch release for each "x" version and records it with its source checksum.

OIIO is not part of the platform specification. The starting OIIO pins are the releases ASWF chose for each year, which are a known-compatible reference. They are not a dependency on ASWF images. The OIIO, OCIO, and OpenEXR release tags were confirmed upstream with `git ls-remote`.

CY2024 is not built (decided 2026-11-02). Its OIIO series, 2.5, requires Boost: `find_package(Boost REQUIRED)` for `thread`, and for `filesystem` too unless the standard library provides it. Every image here leaves Boost out. Moving CY2024 to OIIO 3.x would remove Boost but would no longer match the OIIO 2.5 interface that CY2024 software was built against. CY2024 is also the first year to leave the support window, on 2028-01-01. Its column stays in the table for reference.

## Decisions And Boundaries

**Base images and sources**

- Do not use ASWF build images. Each year builds from a digest-pinned Rocky Linux base:
  - the full image for the compile stage;
  - the minimal variant for the runtime stage.
- Use Rocky packages wherever they match the specification exactly: glibc, and the `gcc-toolset` compiler.
- Build components from pinned upstream source releases, verified by SHA-256, when the specification names a version Rocky does not package, or when exact control matters. That covers CPython, Imath, OpenEXR, OpenColorIO, and OpenImageIO.
- Install NumPy from a pinned, hash-checked wheel. Choose `manylinux_2_28` or older wheels so they run on each year's glibc floor.
- Build CPython from source for every year, including the 3.11 years where Rocky packages 3.11.13. One build path and one install layout for every year outweighs the smaller saving of using a distro package for two years.

**Contents of the image**

- Ship only what OIIO's command-line tools and Python bindings need. Every specified component the image contains must match the specification.
  - Leave out platform components that OIIO does not need: Qt/PyQt/PySide, Boost, oneTBB, oneMKL, Alembic, FBX, OpenSubdiv, OpenVDB, and Ptex. The image makes no compliance claim for those.
  - Disable OIIO plugins that would pull them in.
- Build zlib, libjpeg-turbo, libpng, and libtiff from locked sources too, rather than taking Rocky packages. This was revised during Step 1 after the following findings:
  - OIIO 3.1 requires libjpeg-turbo 2.1 or newer, but Rocky 8 ships 1.5.3 and Rocky 9 ships 2.0.90.
  - OCIO 2.5 requires zlib 1.2.13 or newer, but both Rocky releases ship 1.2.11.
  - Rocky's libtiff links Rocky's `libjpeg.so.62`, which would put two libjpeg builds with the same library name in one process.
- Lock the libraries OCIO would otherwise download (expat, yaml-cpp, pystring, minizip-ng, and the arm64 `sse2neon` header) and link them statically into OCIO. Use OpenEXR's vendored libdeflate and OpenJPH. Every compile step runs with `RUN --network=none`, so a build that tries to download anything fails.
- Install all built components under one prefix, `/opt/vfx`, with an absolute RPATH. The runtime stage copies only that prefix onto the minimal Rocky base, which already provides glibc, `libstdc++`, OpenSSL, libffi, bzip2, and xz. The CentOS 7 approach of copying whole system directories goes away.
- Keep link-time optimization off. On amd64, gcc-toolset-14's `lto1` crashed with an internal compiler error while linking OIIO's pybind11 module.
- gcc-toolset builds link newer C++ runtime pieces statically. The runtime therefore uses the base OS `libstdc++` and must not need any `GLIBCXX` symbol version newer than it provides.

**Tags and build interface**

- Build the years in the platform's support window as of 2027-01-01, when this work is expected to land: CY2024–CY2027. Exclude CY2023, which leaves the window on 2027-01-01. Include CY2027 now because it is Final and studios begin targeting it ahead of its effective date. CY2024 was later excluded too, because its OIIO series requires Boost (see the target matrix), so the images are CY2025–CY2027.
- Tag images `algernon_vfx/oiio:cy<year>`. Keep `algernon_vfx/oiio:latest` pointing at the current calendar year's platform: CY2026 until 2027-01-01, then CY2027.
- The plain `docker build -t algernon_vfx/oiio .` command in the README must keep working. It builds the current year, using defaults from the Dockerfile's build arguments.
- Use one parameterized Dockerfile. A per-year lock, `build/locks/cy<year>.json`, records the pinned versions, URLs, and checksums in the format defined by [Phase 4](04-locked-inputs-and-ci.md). A `docker-bake.hcl` file declares the targets `cy2025` through `cy2027` and a `default` group.
- Keep the non-root `algernon` user and the interactive Bash entry point.

**Platforms and scope**

- Target both `linux/amd64` and `linux/arm64`. `arm64` builds natively on the development host, and `amd64` builds under Docker Desktop's emulation, which is expected to be slow. amd64 remains the platform render farms are most likely to need.
- Defer the following:
  - registry publication;
  - hosted CI;
  - GPU features, OSL, and USD;
  - macOS and Windows builds.
- Phase 2's legacy CY2021 baseline is still useful evidence. Once this matrix is verified, retire the CY2021 recipe instead of repairing it.

## Work Plan

### 1. Confirm Build Inputs

- Recheck the matrix against vfxplatform.com and record any changes. CY2027's OCIO, OpenEXR, and OpenVDB confirmations were still pending when the page was read.
- Check the amd64 repositories for the same packages that were checked on arm64. Confirm that each Rocky release's `gcc-toolset` and runtime packages are available on both architectures.
- Choose the exact patch release for each "x" version: CPython, Imath, OpenEXR, OCIO, and NumPy. Prefer the newest patch release in the specified series. Record URLs and SHA-256 checksums in the `build/locks/` files.
- Check each OIIO starting pin against its release's documented minimum and maximum dependency versions. Identify the Python binding library it needs (pybind11, or whatever later releases use instead), and pin that too.
- Identify the dependencies that OCIO and OpenEXR fetch for themselves, and decide for each whether to pin it explicitly or record the version the project fetches.
- Completion evidence: complete `build/locks/cy<year>.json` files, with the checks and choices recorded in the implementation log.

### 2. Build The Current Year End To End

- Write the parameterized Dockerfile and `docker-bake.hcl`. Implement only the CY2026 target at first, building natively on `linux/arm64`.
- Build the following in order into `/opt/vfx` with `gcc-toolset-14` and `-std=c++20`: CPython 3.13, Imath 3.2, OpenEXR 3.4, OCIO 2.5, NumPy 2.3, and OIIO 3.1.18.1.
- Assemble the Rocky Linux 8 minimal runtime stage.
- Run the year verification described under Validation. Record the image size, then set a size budget for every year based on that measurement.
- Repeat the build for `linux/amd64`.
- Completion evidence: `algernon_vfx/oiio:cy2026` passes verification on both architectures, and the digests and sizes are recorded.

### 3. Extend To The Remaining Years

- Add the CY2025 and CY2027 targets. CY2024 is not built; see the target matrix.
  - CY2025 uses `gcc-toolset-11` with C++17.
  - CY2027 is the only year on Rocky Linux 9.
- Build and verify each year on both architectures.
- Completion evidence: all three tags pass verification on both architectures, within the size budget, with digests recorded.

### 4. Document The Support Contract

- Add `docs/PLATFORMS.md`. For each year, list:
  - the specified versions and the verified versions;
  - the components left out;
  - the image tags, digests, and sizes;
  - any deviations.
- Link `docs/PLATFORMS.md` from the README and the mission, and update the mission's engineering model.
- Update the README with matrix build commands and instructions for choosing a year's image.
- Record the annual maintenance procedure:
  - add a year when it becomes Final (usually late summer);
  - move `latest` on January 1;
  - drop the oldest year when it leaves the support window;
  - refresh base-image digests and security patch releases deliberately.
- Completion evidence: the README and PLATFORMS.md describe only verified behavior.

### 5. Retire The Legacy Recipe

- After step 3 passes, remove the CY2021 build path. Keep its Phase 2 evidence in the log.
- Completion evidence: no Dockerfile path references `centos:centos7` or any ASWF image.

## Validation

Run all of the [Phase 2 checks](02-build-verification.md#validation) against each `algernon_vfx/oiio:cy<year>` image on each architecture. Add a scripted year verification (planned as `scripts/validate_image.py`, which [Phase 4](04-locked-inputs-and-ci.md) extends) that fails on any mismatch with that year's lock:

- `oiiotool --version` equals the pinned OIIO version.
- `python3 --version` equals the pinned CPython version, and `numpy.__version__` equals the pinned NumPy version.
- `import OpenImageIO, PyOpenColorIO` succeeds.
- The OCIO version reported by `PyOpenColorIO.__version__` and by OIIO's dependency list both equal the pinned OCIO version. OIIO's list is `OpenImageIO.get_string_attribute("library_list")`. The OpenEXR and Imath versions reported there must also match.
- `ldd --version` in the runtime equals the year's glibc floor.
- No binary or Python extension requires a `GLIBC_` symbol version newer than that floor, or a `GLIBCXX_` symbol version newer than the base OS `libstdc++` provides. Check with `objdump -T`.
- All binaries and Python extensions resolve without missing libraries. Check with `ldd`.
- No excluded platform component is present. Check that there are no Qt, Boost, TBB, or OpenVDB shared libraries in the image.
- An OCIO color conversion with OCIO's built-in config succeeds. Record which ACES version the built-in config provides, and compare it with the year's specified ACES version.
- The image size is within the budget set in step 2.

Build commands name the platform explicitly, for example `docker buildx bake --set '*.platform=linux/arm64' cy2026`.

## Acceptance Criteria

- `docker buildx bake` builds `algernon_vfx/oiio:cy2025` through `cy2027` for `linux/amd64` and `linux/arm64`, from digest-pinned Rocky Linux bases and checksum-verified sources. No ASWF image is used.
- Every image passes the Phase 2 checks and the year verification script as the `algernon` user, and stays within the recorded size budget.
- Every shipped component named by the platform matches that year's specification. Components left out are listed in `docs/PLATFORMS.md`.
- Every image's runtime glibc equals its year's floor. No shipped binary requires a newer glibc or a newer `libstdc++` than the base OS provides.
- `algernon_vfx/oiio:latest` and the plain README build command produce the current calendar year's image.
- The CY2021 recipe is removed, and its baseline evidence is kept in the implementation log.

## Status

Status: in progress.

- Steps 1 and 2 are complete for CY2026. `algernon_vfx/oiio:cy2026` builds for `linux/amd64` and `linux/arm64` from [build/locks/cy2026.json](../../build/locks/cy2026.json) and passes all 35 validator checks on both. The results are in the [implementation log](../IMPLEMENTATION.md).
- Step 3 is complete. `algernon_vfx/oiio:cy2025` and `cy2027` build for both architectures from [build/locks/cy2025.json](../../build/locks/cy2025.json) and [build/locks/cy2027.json](../../build/locks/cy2027.json) and pass all 35 validator checks. CY2026 and CY2027 were rebuilt and re-validated after each later Dockerfile change. CY2024 is not built because OIIO 2.5 requires Boost; see the target matrix.
- CY2025 deviations from this plan, recorded in the [implementation log](../IMPLEMENTATION.md):
  - OIIO is 3.1.19.0, the same release as CY2026, in place of ASWF's 3.1.6.2 from the same series.
  - OCIO 2.4's helper libraries use CY2026's newer releases rather than OCIO 2.4's older recommendations, and pybind11 is 2.13.6.
  - OCIO 2.4 provides the ACES 2.0 output transforms, but its built-in configs are ACES 1.3, so an ACES 2.0 config must come from outside the image.
- CY2027 deviations from this plan, recorded in the [implementation log](../IMPLEMENTATION.md):
  - OIIO 3.2 builds its Python bindings with nanobind, its new default, instead of pybind11.
  - OIIO 3.2 defaults amd64 SIMD to SSE4.2 (x86-64-v2), which Rocky Linux 9 already requires.
  - OCIO 2.6's default built-in config is ACES 2.1. The ACES 2.0 built-in configs that CY2027 specifies are still included.

Last updated: 2026-11-02
