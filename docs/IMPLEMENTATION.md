# Implementation Log

Record decisions that change project direction, specifications, runtime behavior, tests, validation, dependencies, deployment, or architecture. Link to plans rather than duplicating their details.

## 2026-11-01: Build And Verify CY2026 On Rocky Linux

Request:

- Start Phase 3, beginning with the CY2026 image built from clean Rocky Linux bases.

Decision:

- Step 1 inputs:
  - amd64 Rocky packages match arm64: `gcc-toolset-14` is 14.2.1 on Rocky 8.10, CMake is 3.26.5, and glibc is 2.28.
  - Pinned bases: `rockylinux/rockylinux:8.10` (`sha256:e8a49c54…f2338c6`) and `8.10-minimal` (`sha256:6d2ede10…61c965`).
  - Each component uses the newest patch release in its specified series: CPython 3.13.18, Imath 3.2.3, OpenEXR 3.4.17, OCIO 2.5.2, and NumPy 2.3.5 (`manylinux_2_28` wheels).
  - OIIO is 3.1.19.0, the newest 3.1 patch, in place of ASWF's 3.1.18.1.
- Lock 18 source archives and 2 wheels in [build/locks/cy2026.json](../build/locks/cy2026.json).
  - Build zlib 1.3.1, libjpeg-turbo 3.1.2, libpng 1.6.50, and libtiff 4.7.1 from source, rather than taking Rocky packages. OIIO 3.1 requires libjpeg-turbo 2.1 or newer, OCIO 2.5 requires zlib 1.2.13 or newer, and Rocky's libtiff would bring in a second `libjpeg.so.62`.
  - Lock the libraries OCIO would otherwise download (expat 2.7.2, yaml-cpp 0.8.0, pystring 1.1.4, minizip-ng 4.0.10, and `sse2neon` at OCIO's pinned commit), at OCIO's recommended versions, and link them statically.
  - Lock nasm 3.02, because it is not in Rocky's default repositories.
  - Use the versions recommended by OIIO for fmt 12.1.0, robin-map 1.4.0, and pybind11 3.0.1.
- Add `build/fetch_sources.py`, adapted from ffmpeg-docker. It downloads over HTTPS only, checks every SHA-256 before extracting, and selects wheels by platform.
- Replace the `Dockerfile` with a parameterized Rocky Linux build:
  - all compile steps run with `--network=none`;
  - code is compiled for generic x86-64 or ARMv8-A;
  - everything installs under `/opt/vfx` with an absolute RPATH;
  - the runtime is the minimal base plus `/opt/vfx`, and creates the `algernon` user directly.
  - The CY2021 recipe moved to `legacy/Dockerfile.cy2021` until Step 5.
- Add `docker-bake.hcl` (target `cy2026`, tagged `cy2026` and `latest`), `scripts/validate_image.py`, and `build/image-size-budgets.json`.
- Fixes found during the build:
  - The Rocky 8 builder has no `find`, so the strip step had silently stripped nothing. Add `findutils` and make the step fail on pipeline errors.
  - Drop `-O`/`-OO` bytecode. Together with stripping, this took arm64 from 441 MB to 335 MB.
  - Correct libtiff's option names to `tiff-cxx` and `tiff-opengl`.
  - Turn link-time optimization off. On amd64, gcc-toolset-14's `lto1` hit an internal compiler error (`in return_token, at opts-common.cc:2177`) while linking OIIO's pybind11 module. Native arm64 linked successfully with it. Whether emulation causes the crash is unknown.

Affected areas:

- `Dockerfile`, `legacy/Dockerfile.cy2021`, `docker-bake.hcl`, `.dockerignore`, `build/`, `scripts/validate_image.py`, the README, the Phase 3 plan, the roadmap, and this log.

Validation:

- The fetch helper verified all 19 locked inputs for each platform, and rejected a truncated zlib archive before extracting it.
- The ELF symbol-version parser reports Rocky 8's `libstdc++` as providing up to `GLIBCXX_3.4.25`, which is correct for gcc 8.
- arm64 builds natively in about 4.5 minutes. amd64 builds under emulation in about 12 minutes.
- Configure logs confirm every locked dependency was found, every excluded OIIO plugin was disabled, and OpenEXR used vendored OpenJPH 0.31.0.
- `scripts/validate_image.py` passed all 35 checks on both images:
  - `cy2026-amd64`: `sha256:46d800002a6a7950c849286953acec85a427c72a6268eb8dc760dd2d27108bf4`, 332,072,890 bytes.
  - `cy2026-arm64`: `sha256:f08a5c8302548e04519e3c17dd042e9acd57a430c603de155a9ce07301189511`, 335,312,937 bytes.
- What the checks confirmed:
  - `oiiotool --buildinfo` reports gcc 14.2 with C++20, plus fmt 12.1.0, Imath 3.2.3, libjpeg-turbo 3.1.2, OCIO 2.5.2, OpenEXR 3.4.17, PNG 1.6.50, pybind11 3.0.1, Python 3.13.18, TIFF 4.7.1, and zlib 1.3.1.
  - NumPy is 2.3.5, and the runtime glibc is 2.28.
  - The highest symbol versions required are `GLIBC_2.28` and `GLIBCXX_3.4.22`, both within what the base provides.
  - Every ELF file resolves its libraries, and no excluded libraries are present.
  - EXR, TIFF, PNG, and JPEG round trips, `maketx`, and a NumPy read pass.
  - OCIO's built-in default config is `cg-config-v4.0.0_aces-v2.0_ocio-v2.5`, which provides the ACES 2.0 that CY2026 specifies. An ACES2065-1 to ACEScg conversion succeeds.
- Size budgets: `docker image inspect .Size` reports only compressed content for a freshly loaded image whose platform differs from the engine's (84 MB for amd64). The validator therefore measures size after running containers. The budgets are about 5% above the measured sizes.
- The README's plain `docker build` produces a native arm64 image. Its interactive shell runs as `algernon`.

Follow-up:

- Phase 3 Step 3: CY2024, CY2025, and CY2027.
- For Phase 4:
  - CPU baselines: amd64 OIIO currently builds `sse2` only, and arm64 builds `neon`.
  - OCIO ignored `sse2neon_ROOT` on arm64, so its NEON SIMD path is not enabled.
  - Python bytecode is not yet deterministic.
  - RPM packages are installed without exact version pins beyond the toolset.
  - The plain `docker build` and `buildx --load` produce different image IDs from identical cached layers.
  - Publisher signatures are not yet verified.

## 2026-11-01: Verify Legacy CY2021 Build

Request:

- Start Phase 2: record the legacy build and runtime baseline.

Decision:

- Build only for `linux/amd64`. `aswf/ci-vfxall:2021-clang10.5` (`sha256:ad684a8b099d65a44d2bacb1a54cf9f6d29924705606fa122d34ef2f3d75a1ab`) is amd64-only. On an arm64 host, the README's platform-less build would resolve the runtime base `centos:centos7` (`sha256:be65f488b7764ad3638f236b7b515b3678369a5124c47b8d32916d6487418ea4`) as arm64, and copy amd64 binaries into it. The README now names the platform.
- The unmodified recipe failed. It cloned OIIO `main` at `d1ca012b11b9b00b04c2c0edfce9ae164ee84f17`, whose `build_pybind11.bash` builds pybind11 v3.0.1. pybind11's configure step rejected Python 3.7.9 because it requires at least 3.8.
- Pin the clone to OIIO `v2.2.10.1` from the AcademySoftwareFoundation repository, and verify commit `d51b7b3b34c75d76a5f9620ee7160e56eec6677c`.
  - The base image already ships OIIO 2.2.10, OCIO 2.0.0, OpenEXR and Imath 2.5, gcc 9.3.1, CMake 3.19.3, and Python 3.7.9, on CentOS 7.8 with glibc 2.17. This patch release matches the stack the image was built for.
  - With the pin, the build succeeded. The OIIO compile step took 735 s under emulation.
- Set `LD_LIBRARY_PATH` and `PYTHONPATH` in the runtime stage. The image's `python3` could not load `libpython3.7m.so.1.0`, because the runtime stage did not carry over these variables from the base image. `oiiotool` worked without them only because its RPATH includes `/usr/local/lib` and `/usr/local/lib64`.
- Leave the ineffective `pybind11_DIR` path and the other legacy behavior unchanged. Phase 3 replaces this recipe.

Affected areas:

- Dockerfile: OIIO pin and commit check, plus the runtime library and Python paths.
- README build commands, the Phase 2 plan results, the roadmap, and this log.

Validation:

- Recorded the host and toolchain: Docker 29.9.2 with a `linux/arm64` engine, Buildx 0.38.1, 18 CPUs, and about 8.3 GB of memory available to Docker.
- Image `algernon_vfx/oiio:legacy-cy2021-amd64`: ID `sha256:8fbdc0c96915aba134fe4876250e72a3346abed226ecd34a143e2a273afb206b`, 1,546,593,927 bytes, amd64, user `algernon` (uid 1000). Runtime is CentOS 7.9 with glibc 2.17.
- `oiiotool --help` reports OIIO 2.2.10, built for SSE2, with dependent libraries including OpenEXR 2.5.2, OpenVDB 8.0.0, Ptex, LibRaw 0.19.4, and libtiff 4.0.3. OIIO 2.2 rejects `--version`.
- `iinfo` and `maketx` are on `PATH`, and `ldd` reports no missing libraries for `oiiotool`.
- Python imports `OpenImageIO` 2.2.10 (from `/usr/local/lib64/python3.7/site-packages`) and `PyOpenColorIO` 2.0.0.
- In a mounted scratch directory:
  - `oiiotool --pattern checker 128x128 3 -d half` wrote an EXR that `iinfo` reports as 128×128, three channels, half-float;
  - `maketx` produced a 64×64-tiled, float, MIP-mapped TIFF texture;
  - Python read the EXR as `128 128 3 half`.
- `bash` ran inside the image. The README's `docker run -it --platform linux/amd64 --entrypoint=bash` session opened a prompt as `algernon` on `/dev/pts/0` and exited 0. Neither the agent shell nor the user's `!` prompt has a TTY, so the session ran through macOS `script` as a pseudo-terminal.
- Phase 2 acceptance criteria are met, and the phase is complete.

Follow-up:

- Phase 3 and Phase 4 notes from these results:
  - `oiiotool --version` is unavailable in OIIO 2.2, so confirm the version check against each year's OIIO release.
  - The legacy configure step fetched fmt and robin-map from the network.
  - `oiiotool` carries a leftover build-directory RPATH.
  - The image is 1.55 GB, which sets the size baseline that Phase 3 should shrink.

## 2026-11-01: Plan Locked Inputs And CI

Request:

- Plan the GitHub Actions workflow and the other build checks used in ffmpeg-docker, for this repository.

Decision:

- Add [Phase 4](plans/04-locked-inputs-and-ci.md). It adapts ffmpeg-docker's verified pattern to this repository's year-by-architecture matrix:
  - source and toolchain locks, with checksums verified before extraction;
  - a locked package closure, using Rocky RPMs in place of Debian APT packages;
  - image identity, linkage, and contents validation;
  - an image-format support contract with deterministic fixtures;
  - license collection and per-image size budgets;
  - cold reproducibility checks;
  - a pinned GitHub Actions workflow on native amd64 and arm64 runners.
- Use one lock per year, `build/locks/cy<year>.json`. Phase 3 now records its pins there and names its check `scripts/validate_image.py`, so Phase 4 needs no file migration.
- Record the gaps that differ from ffmpeg-docker:
  - Rocky has no package snapshot service;
  - CY2027 needs an x86-64-v2 floor;
  - Python bytecode must be made deterministic;
  - the GitHub Actions cache limit applies across eight image jobs.
- Hosted CI waits until the user chooses to push. The repository is local-only for now.

Affected areas:

- The Phase 3 and Phase 4 plans, the roadmap, and this log. Build and runtime behavior are unchanged.

Validation:

- Reviewed ffmpeg-docker's workflow, its locks and their supporting scripts, its build environment and provenance documents, and its Phase 3 plan and log.
- Documentation checks only. Nothing was built.

Follow-up:

- Carry out Phase 4 alongside Phase 3, starting with the CY2026 lock and fetch helper.

## 2026-11-01: Plan Reference Platform Build Matrix

Request:

- Plan builds that align with each VFX Reference Platform year listed on vfxplatform.com.

Decision:

- Add [Phase 3](plans/03-reference-platform-matrix.md), which plans one image per year for CY2024–CY2027. This is the support window as of 2027-01-01. CY2023 is excluded because it leaves the window then.
- Do not use ASWF build images. An ASWF `aswf/ci-oiio` approach was drafted first and rejected at the user's direction, in favor of clean, small images built from Rocky Linux as the platform specifies. Rejecting it also removes the 3.5–4.8 GB build images and the amd64-only restriction those images impose.
- Use Rocky Linux 8 for CY2024–CY2026 and Rocky Linux 9 for CY2027, matching each year's glibc floor, with Rocky's `gcc-toolset-11` or `gcc-toolset-14` compiler.
- Build CPython, Imath, OpenEXR, OCIO, and OIIO from checksum-verified sources, and install NumPy from pinned wheels. Leave out platform components that OIIO does not need.
- Target `linux/amd64` and `linux/arm64`. Tag images `cy<year>`, with `latest` tracking the current calendar year. Retire the CY2021 recipe after the matrix is verified.
- Start from the OIIO release ASWF pins for each year (2.5.19.1, 3.1.6.2, 3.1.18.1, and 3.2.1.1) as a compatibility reference only.
- Narrow Phase 2 to a legacy baseline plus reusable checks, so that it does not duplicate Phase 3's modernization.

Affected areas:

- Phase 2 and Phase 3 plans, the roadmap, and this log. Build and runtime behavior are unchanged.

Validation:

- Read vfxplatform.com (page last modified 2026-10-17) for the specified versions.
- Read ASWF `versions.yaml` from aswf-docker `main` for the OIIO reference pins.
- Confirmed with `git ls-remote` that the OIIO and OCIO release tags exist upstream.
- Ran `linux/arm64` containers from `rockylinux/rockylinux:8` (8.10) and `rockylinux/rockylinux:9` (9.8) to record glibc and the available `gcc-toolset`, Python, and NumPy packages; see the plan for the results.
- The amd64 repositories were not checked. Nothing was built.

Follow-up:

- Carry out Phase 2, then Phase 3 starting with the CY2026 target.
- Recheck CY2027's pending component confirmations before claiming CY2027 compliance.

## 2026-11-01: Adopt Project Playbook

Request:

- Update this repository using the documents in `templates/project-playbook`.

Decision:

- Adopt a root agent guide and project-specific documents under `docs/`, keeping the reusable templates. The layout follows the sibling ffmpeg-docker repository.
- Complete the [playbook adoption](plans/01-project-playbook.md), and define [build verification](plans/02-build-verification.md) as the next planned phase. Modernization comes after that phase has produced evidence.
- Require signed commits, consistent with the effective `commit.gpgsign=true` setting from the global Git configuration. Signing has not been exercised.
- Preserve the existing `master` checkout, the staged templates, and the untracked `.idea/` directory. Do not commit or publish during setup.

Affected areas:

- `AGENTS.md`, README navigation, mission, roadmap, Git workflow, phase plans, and this log.
- This adoption does not change build or runtime behavior.

Validation:

- Inspected the repository files, source templates, Git status, effective signing configuration, and the sibling ffmpeg-docker adoption.
- Checked local Markdown links, unresolved template prompts in the adopted documents, and Git whitespace validation.
- Confirmed that the Docker CLI is present. This documentation phase did not test Docker daemon access, image builds, runtime linking, Python imports, or image I/O.

Follow-up:

- Carry out the build verification phase. Static inspection identified likely failure points to check first:
  - the end-of-life CentOS 7 runtime;
  - the unpinned OIIO clone;
  - the `/home/python_user` pybind11 path;
  - the cross-distribution directory copy in the runtime stage.
