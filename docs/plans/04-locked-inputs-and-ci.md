# Plan: Locked Inputs And Automated Verification

## Goal

Make every reference-platform image traceable to exact inputs, and verify it automatically: the same source, toolchain, image-content, size, reproducibility, and CI checks that ffmpeg-docker applies, adapted to a matrix of four platform years and two architectures.

## Current State

- [Phase 3](03-reference-platform-matrix.md) is complete: `cy2025`–`cy2027` images for amd64 and arm64; CY2024 is not built.
  - Base images: digest-pinned Rocky Linux.
  - Compiler: Rocky's `gcc-toolset`.
  - Sources: checksum-verified upstream releases in one lock per year, fetched by `build/fetch_sources.py`, with compile steps run under `--network=none`.
  - Checks: `scripts/validate_image.py`, with unpacked-size budgets.
- The sibling ffmpeg-docker repository has implemented and verified this kind of automation. It consists of:
  - a source lock (`build/dependencies.lock.json`) with signature checks;
  - a toolchain lock (`build/toolchain.lock.json`) covering the base image, the package snapshot, the full package closure, the Dockerfile frontend, BuildKit, and the CI actions;
  - the scripts `validate_lock.py`, `validate_image.py`, `smoke_media.py`, `collect_licenses.py`, and `reproducible_build.py`;
  - per-platform size budgets;
  - `.github/workflows/ci.yml`, which runs cached builds on native amd64 and arm64 runners, plus weekly cold reproducibility builds.
- Its hosted push workflow passed on both architectures. Its scheduled cold-reproducibility job has not run yet.
- This repository is kept local for now. Hosted CI runs only once a branch is pushed to GitHub.

## Decisions And Boundaries

**Reuse and layout**

- Follow ffmpeg-docker's structure, script names, and evidence standards, so maintainers see one pattern across both repositories. Adapt the parts that differ:
  - the year-by-architecture matrix;
  - Rocky's RPM packages in place of Debian's APT packages;
  - image formats in place of media codecs.
- Keep one lock per platform year, `build/locks/cy<year>.json`. Each lock lists that year's sources and toolchain identities. Phase 3 should record its pins in this format from the start, so this phase adds verification rather than migrating files.
- Implement the checks as Python 3 scripts that use only the standard library, as ffmpeg-docker does. Phase 3's year check is `scripts/validate_image.py`, which this phase extends.

**Claims are separate**

- Treat these as four separate claims, each needing its own evidence:
  - locked inputs;
  - matching shipped-binary hashes;
  - matching root filesystem contents;
  - matching image digests.
- Do not call an image reproducible because its versions match.

**Package pinning on Rocky**

- Rocky Linux has no equivalent of Debian's snapshot service. Rocky 8.10 and 9.8 are rolling final or current minor releases, and superseded builds may leave the main repositories.
- Lock the exact name, version, and release of every installed RPM, and fail the build when the installed set differs.
- Task 2 decides from evidence how to keep those packages installable:
  - rely on Rocky's repositories keeping older builds;
  - pin a vault or mirror path;
  - or accept deliberate lock refreshes.

**CPU baselines**

- Set explicit, generic CPU baselines rather than tuning for the build host. Rocky Linux 9 itself requires x86-64-v2 on amd64, so CY2027 cannot go below that.
- Choose the CY2025–CY2026 amd64 baseline and OIIO's `USE_SIMD` setting from evidence, and record them. Confirm them against production workers before deployment.

**CI scope**

- CI covers the full year-by-architecture matrix: 6 image jobs.
- Watch build minutes and the default 10 GB repository cache limit for GitHub Actions. Narrow the cache, not the matrix, if the limit is exceeded.
- Registry publication, image signing and attestations, and release automation remain out of scope.

## Execution Order

1. Complete Phase 3 Steps 1–2 (CY2026 builds end to end). Write the lock file and the fetch helper alongside them.
2. Complete Tasks 1–2 for CY2026, then extend the locks to the other years as Phase 3 Step 3 adds them.
3. Complete Tasks 3–4 against the CY2026 image first, then run them on every year.
4. Complete Task 5, running cold pairs locally before relying on hosted CI.
5. Complete Task 6. Its hosted run happens once the branch is pushed, which is the user's decision.

For each task, record commands, year, platform, results, and unresolved issues in [IMPLEMENTATION.md](../IMPLEMENTATION.md). Keep task checkboxes and phase status current.

## Work Plan

### Task 1: Lock And Verify Every Source

Deliverables:

- `build/locks/cy<year>.json`;
- `build/fetch_sources.py`;
- `scripts/validate_lock.py`;
- `docs/SOURCE_PROVENANCE.md`.

Steps:

- [x] 1. Record the following for CPython, Imath, OpenEXR, OpenColorIO, OpenImageIO, the Python binding library, and each NumPy wheel (per Python version and architecture):
  - version;
  - HTTPS URL;
  - archive name;
  - SHA-256;
  - source root.
- [x] 2. Record every dependency that OCIO or OpenEXR fetches during its CMake build, such as yaml-cpp, pystring, minizip-ng, expat, and libdeflate.
  - Lock each as an explicit archive and point CMake at the pre-fetched copy.
  - The compile stage must make no network requests after fetching.
- [x] 3. Verify upstream signatures where projects publish them, whether GPG detached signatures or Sigstore bundles. Store reviewed keys or identities with the lock.
  - Record each checksum's provenance: publisher checksum, verified signature, or computed locally.
- [x] 4. Implement the fetch helper:
  - download over HTTPS only, rejecting redirects to anything else;
  - fail on HTTP errors;
  - check the SHA-256 and signature before extracting anything.
- [x] 5. Remove every version and URL definition from the Dockerfile. Build arguments select a year's lock, never individual sources.
- [x] 6. Make `validate_lock.py` check that every lock is complete and consistent with the [Phase 3 matrix](03-reference-platform-matrix.md#target-matrix). It must also show that a deliberately wrong checksum stops before extraction.
- [x] 7. Document the lock update procedure in `docs/SOURCE_PROVENANCE.md`.

Completion evidence: every built source appears in a lock. All years fetched and verified their locked identities on both architectures. A checksum mismatch stops before extraction. The compile stages build with network access disabled after fetching.

### Task 2: Pin The Build Environment

Deliverables:

- the `toolchain` section of each lock, covering per-architecture RPM package closures for the builder and runtime;
- `build/verify_rpm_lock.py`;
- `docs/BUILD_ENVIRONMENT.md`.

Steps:

- [x] 1. Pin `rockylinux/rockylinux:8.10`, `:9.8`, and their minimal runtime variants by multi-platform index digest. Record the amd64 and arm64 manifest digests.
- [x] 2. Lock the exact name, version, and release of every installed RPM, including the build tools and transitive dependencies, for each base image and architecture.
  - `verify_rpm_lock.py` runs inside the build and fails it if the installed set differs.
  - Decide and document how locked packages stay installable.
  - Decision: install exact builds from the year's own Rocky minor release, at its `pub` path with the `vault` path as a fallback. Rocky keeps superseded builds within a minor release and moves a retired release to `vault`. See [BUILD_ENVIRONMENT.md](../BUILD_ENVIRONMENT.md#rpm-packages).
- [x] 3. Record the identities of gcc, binutils, CMake, Ninja or Make, and glibc. Remove unrestricted `dnf update` from the build.
- [x] 4. Set explicit per-architecture CPU baselines and OIIO SIMD options. Do not tune for the host.
- [x] 5. Pin the Dockerfile frontend and BuildKit image by digest, using the same versions as ffmpeg-docker unless there is a reason to differ: `docker/dockerfile:1.7.1` and `moby/buildkit:v0.33.1`. Record the Buildx version, and document how to create the pinned builder.
- [x] 6. Run two independent `--no-cache` builds per year and architecture, and confirm the source, package, base-image, and toolchain identities match.

Completion evidence: identical input identities across clean builds for every year and architecture. A modified package set fails the build.

### Task 3: Define And Test The Image Support Contract

Deliverables:

- `docs/IMAGE_SUPPORT.md`;
- `scripts/smoke_images.py`;
- deterministic test fixtures.

Steps:

- [x] 1. Define the capability matrix:
  - image formats and bit depths: OpenEXR half and float (scanline, tiled, multipart), TIFF 8/16/float, PNG 8/16 with alpha, JPEG, and DPX;
  - texture creation with `maketx`;
  - OCIO conversions, including which ACES config each year provides;
  - Python and NumPy pixel access;
  - mounted input and output.
- [x] 2. Map each capability to the OIIO plugins and the Rocky or locked libraries that provide it. Disable plugins that are outside the matrix, and record what each year excludes.
- [x] 3. Generate redistributable fixtures outside the image with fixed pixel hashes. `iinfo --hash` reports the pixel hash of each decoded image.
- [x] 4. Write `smoke_images.py`. It runs the round trips for each format, `maketx`, an OCIO conversion, and a Python read, and fails on any wrong dimensions, channel count, data type, or pixel hash.
- [x] 5. Run the matrix on every year and architecture. Publish the contract and link it from the README and the mission.
  - Decision: the contract lives in `build/image-support.json`, and `validate_lock.py` checks that it accounts for every OIIO plugin and that the Dockerfile disables each excluded one. Fixtures are written by `scripts/generate_test_images.py` with the standard library alone, so their pixel hashes do not depend on OIIO. 10-bit DPX is checked as RGB, because OIIO's reader drops the last alpha sample of some 10-bit RGBA rows.

Completion evidence: every capability in the matrix passes on all years and both architectures. The support documentation lists every exclusion.

### Task 4: Validate Image Identity, Linkage, And Contents

Deliverables:

- `scripts/validate_image.py`;
- `scripts/collect_licenses.py`;
- `build/image-size-budgets.json`.

Steps:

- [ ] 1. Check the shipped versions against the year's lock: OIIO, OCIO, OpenEXR, Imath, Python, and NumPy, with OCIO also checked through OIIO's `library_list`.
- [ ] 2. Check the glibc floor and the `GLIBC_` and `GLIBCXX_` symbol-version limits, and confirm `ldd` resolves every library.
- [ ] 3. Check the image contents. Absent: compilers, CMake, headers, static archives, sources, and the excluded platform libraries (Qt, Boost, TBB, OpenVDB). Present: the `algernon` user and Bash.
- [ ] 4. Strip shipped binaries. Keep debug copies only in the build stage.
- [ ] 5. Collect the license and notice files for every shipped component, including statically linked dependencies, into the runtime image.
- [ ] 6. Measure each year and architecture by its unpacked size, the sum of its layer sizes from `docker history --human=false`, and set a budget for each in `image-size-budgets.json`. Fail on an overrun that has not been reviewed. Do not use `docker image inspect .Size`, the metric ffmpeg-docker uses: with Docker Desktop's containerd image store it also counts the compressed layers. Phase 3 already moved the validator to the unpacked size.

Completion evidence: the validator passes for all six images, and fails on a deliberate version mismatch, a missing library, a leftover compiler, and a size overrun.

### Task 5: Make Builds Reproducible

Deliverables:

- `scripts/reproducible_build.py`;
- deterministic build settings in the Dockerfile.

Steps:

- [ ] 1. Set `SOURCE_DATE_EPOCH=0`, the `C` locale, and UTC for builds. Use fixed source paths.
- [ ] 2. Make Python bytecode deterministic for CPython's standard library and for NumPy.
  - Compile `.pyc` files with checked-hash invalidation, or leave them out, rather than relying on timestamps.
  - This source of differences does not exist in ffmpeg-docker.
- [ ] 3. Normalize file modification times on the runtime artifacts and their parent directories. Account for container paths that ffmpeg-docker found Docker Desktop injects, such as `/root/.cache/rosetta`, and for the `/etc` timestamp that `docker export` changes.
- [ ] 4. Build each year and architecture twice in isolated work directories without cache. Then:
  - compare the hashes of shipped executables, shared libraries, and Python extensions;
  - compare the root filesystem's contents and metadata;
  - report config and manifest digests separately.
- [ ] 5. Resolve differences until the shipped-binary hashes match. Report image-digest equality as a separate result.

Completion evidence: local cold pairs match on shipped binaries for every year and architecture, with filesystem and digest results recorded separately.

### Task 6: Add GitHub Actions CI

Deliverables:

- `.github/workflows/ci.yml`;
- a CI section in `docs/BUILD_ENVIRONMENT.md`.

Steps:

- [ ] 1. Add a `lock-validation` job that runs `validate_lock.py` and Python syntax checks on `ubuntu-24.04`.
- [ ] 2. Add an `image-validation` job: a matrix of `cy2025`–`cy2027` × `linux/amd64` (`ubuntu-24.04`) and `linux/arm64` (`ubuntu-24.04-arm`), with `fail-fast: false`.
  - It uses the pinned Buildx and BuildKit, and a GitHub Actions cache scoped to each year, architecture, and branch.
  - It runs `validate_image.py` and `smoke_images.py`.
- [ ] 3. Add a `cold-reproducibility` job that runs on the weekly schedule and on manual runs, covering the same matrix with `reproducible_build.py`.
- [ ] 4. Trigger on pull requests, on pushes to `master`, on a weekly schedule, and on manual runs. Grant `contents: read` permissions only. Pin each action by full commit SHA, matching ffmpeg-docker unless a newer reviewed version is needed:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1);
  - `docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069` (v4.4.1);
  - `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` (v4.6.2).
  - Record these in the toolchain locks.
- [ ] 5. Upload the following as per-job artifacts: the lock files, Buildx metadata, validation and smoke-test results, artifact hashes, and image sizes.
- [ ] 6. Measure job durations and cache use. Adjust cache scope or mode, or set timeouts, from evidence.
- [ ] 7. After the user pushes the branch, confirm a hosted run passes. Separately, confirm a manual run of the cold-reproducibility job.

Completion evidence: a recorded hosted run in which all six image jobs pass, and a recorded manual cold-reproducibility run. CI fails on an invalid checksum, a version mismatch, a missing capability, a glibc limit violation, and a size overrun.

## Validation

- While planning: check Markdown links, unresolved template prompts, whitespace, and consistency with the roadmap and Phase 3. Creating this plan involves no Dockerfile change and no build.
- While executing: reuse the [Phase 2](02-build-verification.md#validation) and [Phase 3](03-reference-platform-matrix.md#validation) checks, and extend them with each task's completion evidence. Exercise each failure path deliberately, not only the passing path.
- Run local checks on both architectures before relying on hosted CI. arm64 runs natively on the development host, and amd64 runs under emulation.

## Acceptance Criteria

- All six tasks are complete, with results linked from the implementation log.
- Every source, wheel, RPM, base image, and build tool has a fixed identity. Sources are verified before use, and compile stages make no network requests.
- Every image passes identity, linkage, contents, license, support-contract, and size-budget checks on both architectures.
- Independent cold builds produce matching shipped-binary hashes for each year and architecture. Image-digest results are reported separately.
- Hosted CI enforces all of the above for the full matrix, with a recorded passing run.
- The README, mission, build environment, source provenance, and image support documents describe the implemented behavior.

## Reference Guidance

- ffmpeg-docker's `docs/plans/03-small-deterministic-image.md`, `docs/BUILD_ENVIRONMENT.md`, `docs/SOURCE_PROVENANCE.md`, and `.github/workflows/ci.yml`: the patterns this phase adopts.
- [Docker build best practices](https://docs.docker.com/build/building/best-practices/): image pinning and separating build stages.
- [Reproducible Builds: SOURCE_DATE_EPOCH](https://reproducible-builds.org/docs/source-date-epoch/): timestamp control.

## Status

Status: in progress.

- Task 1 is complete; see [SOURCE_PROVENANCE.md](../SOURCE_PROVENANCE.md) and the [implementation log](../IMPLEMENTATION.md).
- Task 2 is complete; see [BUILD_ENVIRONMENT.md](../BUILD_ENVIRONMENT.md). Locked RPMs install from each year's Rocky minor release, with a `vault` fallback that has not yet been exercised.
- Task 3 is complete; see [IMAGE_SUPPORT.md](../IMAGE_SUPPORT.md). Every year and architecture passes `smoke_images.py`, and OIIO's formats outside the contract are disabled.

Last updated: 2026-11-07
