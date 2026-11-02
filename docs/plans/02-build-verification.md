# Plan: Build Verification

## Goal

Establish and document a working build and runtime baseline for the OIIO image, fixing demonstrated failures with focused changes.

## Current State

- The Dockerfile was last changed in April 2021 ("ASWF 2021 base with python 3.7.9"). It has not been built since this documentation was adopted.
- Compile stage: based on `aswf/ci-vfxall:2021-clang10.5`, which is unpinned by digest. The stage works as follows:
  - It installs `pybind11` with both `pip` and `pip3`.
  - It clones OIIO from its default branch with no tag or commit pinned.
  - It runs OIIO's `build_pybind11.bash`, then configures CMake with `-Dpybind11_DIR=/home/python_user/.local/lib/python3.7/site-packages` and `-DOIIO_BUILD_TOOLS=ON`.
  - It builds with `make && make install`.
- The configured `pybind11_DIR` refers to `/home/python_user`, which the Dockerfile never creates. The build runs as root, while the working directory belongs to `build_user`. Whether CMake ignores, falls back from, or fails on this path is unknown.
- Runtime stage: based on `centos:centos7`. It copies `/bin`, `/usr/lib`, `/usr/lib64`, `/usr/bin`, `/usr/include`, `/usr/share`, and the `/usr/local` subtrees from the compile stage over the CentOS base. It also copies the OIIO build's `bin` directory into `/usr/local/bin` and switches to the user `algernon`.
- Nothing has yet verified any of the following:
  - that the runtime image finds OIIO's shared libraries;
  - that the runtime `python3` has a version that matches the installed `OpenImageIO` module;
  - that `PyOpenColorIO` is importable.

## Decisions And Boundaries

- Choose the target platform and the required tools, formats, and Python version before making broad dependency changes.
- Preserve the `algernon_vfx/oiio` tag, the interactive Bash entry point, and the non-root runtime user unless the plan records a deliberate revision.
- Diagnose build failures in order. Record every change to source locations, versions, base images, and runtime dependencies together with its evidence.
- Pin the OIIO source to a recorded release tag or commit before claiming that a build succeeded. A build of a moving branch is not a baseline.
- CY2021 is outside the VFX Reference Platform support window, and [Phase 3](03-reference-platform-matrix.md) replaces this recipe. Fix only what is needed to record a baseline and prove the validation checks. Leave base-image and OIIO-version replacements to Phase 3.
- Defer the following to a later phase:
  - moving to a newer VFX Reference Platform year (Phase 3);
  - registry publication;
  - GPU or OSL integration;
  - general pipeline orchestration.

## Work Plan

### 1. Capture The Baseline

- Check Docker daemon access, and record the host architecture, target platform, Docker version, and base image digests.
- Try the current build and capture either the first actionable failure or the identity of the resulting image.
- Record the OIIO commit that was built. Do not call the recipe reproducible.

### 2. Fix Demonstrated Build And Runtime Failures

- Fix source retrieval, the pybind11 configuration, compiler compatibility, or the runtime base as the evidence requires. Pin the OIIO release in the process.
- Inspect the following in the resulting image:
  - `oiiotool --version`;
  - the format list reported by `oiiotool --help`;
  - `iinfo` and `maketx` startup;
  - the OCIO version that OIIO reports.
- Confirm that the `OpenImageIO` and `PyOpenColorIO` Python modules import under the runtime user's `python3`.

### 3. Exercise Image I/O And Document Usage

- Generate a synthetic OpenEXR image with `oiiotool`, inspect it with `iinfo`, and convert it to a tiled texture with `maketx`.
- Read the same file from Python.
- Confirm that output written to a mount is writable by the `algernon` user, and that the interactive Bash entry point works.
- Update the operator instructions and the implementation log with the actual results and any unresolved limitations.

## Validation

Run these from the repository root on the selected Docker platform. They are planned checks, not recorded results:

```sh
docker version
docker build --progress=plain -t algernon_vfx/oiio .
docker image inspect algernon_vfx/oiio
docker run --rm --entrypoint oiiotool algernon_vfx/oiio --version
docker run --rm --entrypoint oiiotool algernon_vfx/oiio --help
docker run --rm --entrypoint bash algernon_vfx/oiio -lc \
  'command -v oiiotool iinfo maketx && python3 --version'
docker run --rm --entrypoint python3 algernon_vfx/oiio -c \
  'import OpenImageIO as oiio, PyOpenColorIO as ocio; print(oiio.__version__, ocio.__version__)'

mkdir -p /tmp/oiio-docker-smoke && chmod 777 /tmp/oiio-docker-smoke
docker run --rm -v /tmp/oiio-docker-smoke:/work -w /work --entrypoint oiiotool \
  algernon_vfx/oiio --pattern checker 128x128 3 -d half -o smoke.exr
docker run --rm -v /tmp/oiio-docker-smoke:/work -w /work --entrypoint iinfo \
  algernon_vfx/oiio -v smoke.exr
docker run --rm -v /tmp/oiio-docker-smoke:/work -w /work --entrypoint maketx \
  algernon_vfx/oiio smoke.exr -o smoke.tx
docker run --rm -v /tmp/oiio-docker-smoke:/work -w /work --entrypoint python3 \
  algernon_vfx/oiio -c \
  'import OpenImageIO as oiio; b = oiio.ImageBuf("smoke.exr"); print(b.spec().width, b.spec().height, b.spec().nchannels, b.spec().format)'
```

The `iinfo` and Python output should report a 128x128, three-channel, half-float OpenEXR image, and `smoke.tx` should exist. Use a fresh output directory for each independent run. Adapt the mount path if the host cannot share `/tmp` with Docker.

## Acceptance Criteria

- An image builds on the documented target platform. The build inputs, including the OIIO revision and base image digests, are recorded with the image identity.
- `oiiotool`, `iinfo`, and `maketx` start without missing-library errors in the runtime stage.
- `OpenImageIO` and `PyOpenColorIO` import under the runtime user's `python3`.
- The OpenEXR round trip, the texture conversion, and the write to a mounted directory succeed as the `algernon` user.
- The README's build and shell commands work as documented, or are updated to match the verified behavior.
- Every failure and fix is recorded in the implementation log.

## Status

Status: planned

Last updated: 2026-11-01
