# Implementation Log

Record decisions that change project direction, specifications, runtime behavior, tests, validation, dependencies, deployment, or architecture. Link to plans rather than duplicating their details.

## 2026-11-07: Define And Test The Image Support Contract (Phase 4 Task 3)

Request:

- Work on Phase 4 Task 3.

Decision:

- The supported formats are OpenEXR, TIFF, PNG, JPEG, and DPX. Every other OIIO format plugin is disabled: the 16 built-in ones (BMP, Cineon, DDS, FITS, HDR, ICO, IFF, `null`, PNM, PSD, RLA, SGI, Softimage, Targa, `term`, and Zfile) with new `-DENABLE_<FORMAT>=OFF` options, joining the library-backed plugins that were already off. The exclusions are the same in every year.
- `build/image-support.json` is the machine-readable contract: enabled and excluded plugins with their CMake options, fixture identities, expected pixel hashes, and each year's OCIO built-in configs, default config, default display and view, and display-transform hashes. `validate_lock.py` now checks that it accounts for all 32 plugins in OIIO 3.1 and 3.2, that the Dockerfile disables each excluded one, and that the generator reproduces its fixtures.
- `scripts/generate_test_images.py` writes four 67×43 RGBA fixtures (8- and 16-bit PNG, half and float uncompressed OpenEXR) with the standard library alone, so their pixel hashes are computed without OIIO. They matched `iinfo --hash` exactly on first use.
- `scripts/smoke_images.py` runs 33 checks in one container per image, as the calling user, without network access, with the fixtures mounted read-only. It covers the plugin list, a refused excluded format, fixture reads, 11 round trips, a multipart EXR, `maketx`, OCIO configs and conversions, Python reads and writes, and mounted output compared on the host. Lossless round trips must reproduce the source fixture's hash; the 10-bit DPX hash is derived by the generator; the JPEG hash is frozen.
- 10-bit DPX is checked as RGB. OIIO's DPX reader drops the last alpha sample of a 10-bit RGBA row when the row leaves one sample in its last 32-bit word (widths one more than a multiple of three, such as 1024 and 4096). The raw file holds the correct sample, so the reader is at fault. Reproduced with OIIO 3.1.19.0 and 3.2.2.0, using random 10-bit data at several widths; RGB and single-channel files were unaffected. OIIO PR #5298 fixed a related single-channel case only, and no upstream report was found.
- OIIO converts 16-bit samples to 10-bit DPX by truncation, not rounding; the derived hash depends on it.
- The OCIO display transform differs between amd64 and arm64 by one 8-bit code value in one or two pixels, from OCIO's SIMD paths, so its hash is recorded per architecture. CY2026 and CY2027 produce the same hashes with their different default configs. The ACES2065-1 to ACEScg conversion is compared numerically with the AP0-to-AP1 matrix instead.
- Document the contract in [IMAGE_SUPPORT.md](IMAGE_SUPPORT.md), including the recommended `--user "$(id -u):$(id -g)"` for writing to mounts.

Affected areas:

- The Dockerfile's OIIO configure step, `build/image-support.json`, `scripts/generate_test_images.py`, `scripts/smoke_images.py`, `scripts/validate_lock.py`, IMAGE_SUPPORT.md, PLATFORMS.md, the README, the mission, the Phase 4 plan, the roadmap, and this log.

Validation:

- `validate_lock.py` passes. It rejected a Dockerfile with `-DENABLE_TARGA=OFF` removed and a plugin catalog with an extra entry.
- Before the Dockerfile change, `smoke_images.py` failed the Task 2 CY2026 arm64 image on the plugin list and the excluded-format check, as expected, and passed the pixel checks.
- On the rebuilt CY2026 arm64 image, a contract with a wrong JPEG hash failed that check and exited 1, and a contract with a wrong fixture hash stopped before any check.
- All six images were rebuilt on the pinned builder and pass all 36 `validate_image.py` checks and all 33 `smoke_images.py` checks. Every round trip, `maketx`, and Python hash was identical across years and architectures. ACEScg conversion error was 6.9e-7 (arm64) and 9.1e-7 (amd64).
- Disabling the plugins shrank each image by 0.8–1.2 MB unpacked. Image IDs and sizes are in PLATFORMS.md.
- The amd64 images were built and checked under emulation on an arm64 host.

Follow-up:

- Decide whether to report the 10-bit RGBA DPX reader defect upstream.
- Task 4 is next: image identity, linkage, contents, and license checks.

## 2026-11-05: Pin The Build Environment (Phase 4 Task 2)

Request:

- Work on Phase 4 Task 2.

Decision:

- Keep locked RPMs installable by installing exact builds from each year's own Rocky minor release. Evidence: Rocky 8.10's BaseOS still offered seven `openssl-devel` builds, so superseded builds stay in a minor release; and a retired release (9.7) keeps only a README under `pub` while `vault` serves its repositories. `build/rpm/<year>/rocky.repo` names BaseOS and AppStream at `pub/rocky/<minor>/`, with `vault/rocky/<minor>/` as dnf's fallback URL, over HTTPS with package signature checks and no mirror list.
- `build/rpm/<year>/` holds per-architecture lists: the exact NEVRAs to install (`builder-*`), the full installed builder set (`resolved-*`), and the runtime base's set (`runtime-*`). The Dockerfile installs the builder list with weak dependencies off, and `build/verify_rpm_lock.py` fails the build on any difference. The requested packages moved from the Dockerfile to each lock's `toolchain.rpm.requested`; `scripts/resolve_rpm_lock.py` regenerates the lists.
- Each lock records both per-architecture manifest digests for its base images, and the gcc, g++, binutils, CMake, Make, and glibc versions in `toolchain.tools`. They match what the builds used before: for example, CY2026 gcc 14.2.1-11.el8_10 and CMake 3.26.5-2.el8. Ninja is not used.
- CPU baselines are per year, set by a new `AMD64_MARCH` bake argument and recorded in `toolchain.cpu_baselines`. CY2025 and CY2026 keep x86-64-v1. CY2027 moves to x86-64-v2, which Rocky 9 itself requires, so no hardware is lost. OIIO is configured with an explicit empty `USE_SIMD`, so the `-march` baseline alone sets its SIMD. For OIIO 3.2 this replaces its own `sse4.2` default with the same features from `-march`.
- Pin BuildKit to `moby/buildkit:v0.33.1` by digest, matching ffmpeg-docker, through a `docker-container` builder named `oiio-pinned`. The Dockerfile frontend was already pinned. `build/docker-build-tools.json` records both, plus the observed Buildx 0.38.1 and Docker Engine 29.9.2.
- `validate_lock.py` now checks the repo files, package lists, requested packages, tool versions, manifest digests, the CPU baseline arguments, the frontend digest, and that the Dockerfile runs no `dnf update`. `validate_image.py` checks the runtime RPM set.
- Document the environment in [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md).

Affected areas:

- The Dockerfile's builder stage and OIIO configure step, `docker-bake.hcl`, the three locks, `build/rpm/`, `build/verify_rpm_lock.py`, `build/docker-build-tools.json`, `scripts/resolve_rpm_lock.py`, `scripts/validate_lock.py`, `scripts/validate_image.py`, BUILD_ENVIRONMENT.md, PLATFORMS.md, the README, the mission, the Phase 4 plan, the roadmap, and this log.

Validation:

- `scripts/resolve_rpm_lock.py` resolved all three years on both architectures. Package counts are in BUILD_ENVIRONMENT.md; the architectures differ only by `glibc-headers` (CY2027 x86_64) and `libatomic` (in the CY2027 arm64 base).
- Run against the unmodified Rocky 8.10 base, `verify_rpm_lock.py` failed, listing the missing packages and the three older base builds the lock upgrades.
- Two `--no-cache` builds of the `sources` stage on the pinned builder, for each year and architecture, produced identical identity records: base image digest, RPM manifest digest, and every source checksum and signature. RPM manifest SHA-256s: CY2025 `182ee783…` (amd64) and `fee22e1d…` (arm64); CY2026 `f6e79733…` and `dbcd7b8e…`; CY2027 `8160a979…` and `fc3f6558…`.
- All six images were built on the pinned builder and passed all 36 validator checks, including the new runtime RPM check. Unpacked sizes are unchanged except CY2027 amd64, which grew by 200,704 bytes to 316,108,800, within its budget.
- Compared file by file with the Task 1 images, CY2026 arm64 differs only in the six known build-date files. CY2027 amd64 differs in 89 of 1,587 files, all compiled code, from the x86-64-v2 baseline. Its OIIO still reports `sse2,sse3,ssse3,sse41,sse42`.
- The amd64 images were built and checked under emulation on an arm64 host.

Follow-up:

- When Rocky retires 8.10 or 9.8, confirm a cold build installs through the `vault` fallback.
- Confirm the CPU baselines against the production workers.
- Task 3 is next: the image support contract and `smoke_images.py`. Done on 2026-11-07.

## 2026-11-03: Verify Sigstore Bundles Offline

Request:

- Remove the `sources` stage's dependency on reaching Sigstore during verification.

Decision:

- Pin the public Sigstore trust root as `build/keys/sigstore-trusted-root.json` and pass it to `cosign verify-blob --trusted-root`. Without it, `cosign` fetched the trust root from `tuf-repo-cdn.sigstore.dev` on every cold build.
- Each Sigstore entry in the locks names the file and pins its SHA-256 in `trusted_root` and `trusted_root_sha256`, following the GPG entries' `key_file` and `fingerprint`. The helper checks the hash before running `cosign`.
- The file came from the locked `cosign` 3.1.3's own TUF fetch (root version 16, targets version 14). Its SHA-256, `6494e21e…`, matches the TUF `targets.json` and sigstore/root-signing's `targets/trusted_root.json`.
- `validate_lock.py` checks the pinned hash against the file and shows that a mismatched trust root stops the helper before `cosign` runs and before extraction.
- The refresh procedure for a future key rotation is in [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md#lock-update-procedure).

Affected areas:

- `build/fetch_sources.py`, `build/keys/sigstore-trusted-root.json`, the three locks, `scripts/validate_lock.py`, SOURCE_PROVENANCE.md, and this log.

Validation:

- In a `--network=none` Rocky 9.8 arm64 container, the locked `cosign` without a trust root failed: `tuf refresh failed: Get "https://tuf-repo-cdn.sigstore.dev/15.root.json" … network is unreachable`. With `--trusted-root`, it printed `Verified OK` for Imath 3.2.3 and rejected the same bundle against the `v3.2.2` workflow identity.
- In the same offline container, with the repository mounted read-only, `fetch_sources.py --verify-archive imath` verified the SHA-256 and the Sigstore signature through the pinned trust root.
- `scripts/validate_lock.py` passes, including the new trust-root rejection.
- The `sources` stage passed for all three years on both architectures, with the same counts as before: 21 checksums for CY2025 and CY2027 and 20 for CY2026, 5 GPG signatures, and 3 Sigstore bundles for CY2025 and 4 for CY2026 and CY2027.
- The images were not rebuilt. The change affects only how bundles are verified; the verified archives and their checksums are unchanged.

## 2026-11-03: Verify Source Signatures (Phase 4 Task 1)

Request:

- Start Phase 4. For the Sigstore-signed ASWF sources, switch to the signed release tarballs and verify their bundles in the build (the user's choice of three options).

Decision:

- Restore GPG verification to `build/fetch_sources.py`, following ffmpeg-docker: a signature must verify and come from the pinned primary-key fingerprint. Five projects sign the files the locks use: zlib, libjpeg-turbo, libtiff, expat, and CPython. Their keys are in `build/keys/`, fetched from keys.openpgp.org under each maintainer's verified address. The libjpeg-turbo fingerprint matches libjpeg-turbo.org, and the CPython keys match python.org's release managers. CPython 3.11.18 is signed by Pablo Galindo Salgado's signing subkey `FFE87404168BD847`, and expat by a subkey of Sebastian Pipping's key.
- Imath, OpenEXR, OCIO, and OIIO sign release tarballs with Sigstore, not the GitHub tag archives the locks used. Switch the 11 affected entries to the signed tarballs. For each, the tarball unpacked to exactly the same files as the tag archive. OCIO 2.4.2 (CY2025) publishes no signed tarball and stays a checksum-only tag archive, as the one exception `validate_lock.py` allows.
- Verify each Sigstore bundle in the `sources` stage with `cosign` 3.1.3 (released 2026-08-06; v3.1.4 was two weeks old), locked as a new `tool` kind per platform by its publisher checksum. The identity must be the project's `.github/workflows/release-sign.yml@refs/tags/v<version>` with GitHub's OIDC issuer. `cosign` is fetched and checked first and never shipped.
- The signature checks run after the SHA-256 and before extraction. A named fetch also takes the locked tools.
- Add `scripts/validate_lock.py`. It checks each lock's completeness, the source set per year, the specification series, signature coverage, key files against pinned fingerprints, and Sigstore tags. It checks `docker-bake.hcl` arguments against each lock and the Dockerfile defaults against CY2026. It also checks that the Dockerfile names no source URLs, and that a bad checksum and a bad GPG signature both stop the helper before extraction.
- NASM, libpng, libdeflate, yaml-cpp, pystring, minizip-ng, `sse2neon`, pybind11, fmt, robin-map, and nanobind publish no signatures for the locked files; libpng's signature URLs returned 404.
- Document the policy, keys, limits, and lock update procedure in [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md).

Affected areas:

- `build/fetch_sources.py`, `build/keys/`, the three locks, the Dockerfile's `sources` stage, `scripts/validate_lock.py`, SOURCE_PROVENANCE.md, PLATFORMS.md, the README, the mission, the Phase 4 plan, the roadmap, and this log.

Validation:

- `docker buildx bake` with `target=sources` and `output=type=cacheonly` passed for all three years on both architectures. Each verified every SHA-256 (21 inputs per platform for CY2025 and CY2027, 20 for CY2026), plus 8 signatures for CY2025 and 9 for CY2026 and CY2027.
- In the Rocky 8 builder, `cosign` verified Imath's bundle and rejected the same bundle against a different file.
- `scripts/validate_lock.py` passes. On scratch copies of the repository, it failed with a specific message for a wrong fingerprint, an OCIO version outside the specified series, a bake argument that differs from the lock, and a URL in the Dockerfile.
- All six images were rebuilt and passed all 35 validator checks at their previous unpacked sizes. The new image IDs are in PLATFORMS.md.
- A file-by-file comparison of `/opt/vfx` against the previous arm64 images found no added or removed files. OIIO, OCIO, OpenEXR, and Imath are byte-identical. Only six files and the `.pyc` files differ: libjpeg-turbo's three tools and two libraries, which embed the build date (`build 20261103`), and `libpython`, which embeds its build time in `sys.version`.
- A first attempt to bake all three arm64 years at once ran out of memory in OCIO's compile step (8 jobs per year on an 8 GB Docker VM). Building one year at a time succeeded.

Follow-up:

- Task 5: build dates in libjpeg-turbo and CPython, and timestamped `.pyc` files.
- Sebastian Pipping's expat signing subkey expires on 2026-12-28; recheck the expat signature after that date.
- Task 2 is next: lock the RPM package closures.

## 2026-11-02: Budget The Unpacked Image Size

Request:

- Fix the size metric before merging Phase 3.

Decision:

- With Docker Desktop's containerd image store, `docker image inspect .Size` is the unpacked layers plus the compressed layers. For each arm64 image, the layer sizes plus the `docker save` output (the compressed blobs) match `.Size` to within 1 MB. Every size recorded earlier in this log and in PLATFORMS.md therefore overstated the images by their compressed size, including the base sizes (Rocky 8.10 minimal "147 MB" and Rocky 9.8 minimal "242 MB").
- The validator now budgets the unpacked size: the sum of the layer sizes from `docker history --human=false`. It means the same thing with the classic image store that hosted CI will use. `.Size` is still printed for reference, and an unpacked size of 0 fails the check.
- Budgets are the new measurements plus about 5%. PLATFORMS.md lists unpacked and compressed sizes, and the Phase 4 plan now uses this metric in place of ffmpeg-docker's `.Size`.

Affected areas:

- `scripts/validate_image.py`, `build/image-size-budgets.json`, PLATFORMS.md, the README, the Phase 4 plan, and this log. No image changed.

Validation:

- Unpacked and compressed sizes of the recorded images:

  | Image | Unpacked | Compressed (`docker save`) | Earlier `.Size` |
  | --- | --- | --- | --- |
  | cy2025 amd64 | 272,252,928 | 88,574,464 | 360,809,384 |
  | cy2025 arm64 | 262,311,936 | 82,373,632 | 344,667,356 |
  | cy2026 amd64 | 247,902,208 | 84,188,672 | 332,072,890 |
  | cy2026 arm64 | 256,081,920 | 79,249,408 | 335,312,937 |
  | cy2027 amd64 | 315,908,096 | 106,739,200 | 422,629,705 |
  | cy2027 arm64 | 333,832,192 | 103,256,064 | 437,070,594 |

- Base layers unpacked: Rocky 8.10 minimal is 104,292,352 bytes (amd64) and 109,686,784 (arm64); Rocky 9.8 minimal is 173,113,344 and 182,460,416.
- `scripts/validate_image.py` passed all 35 checks on all six `cy<year>-<arch>` images with the new metric and budgets.
- With the CY2026 arm64 budget lowered to 256,000,000 bytes, below its measurement, the size check failed as expected. The budget was then restored.

Follow-up:

- Possible reductions, not yet made: NumPy's test suite (15 MB per image), CPython's `_test*` extension modules (about 1 MB), and, in Phase 4, a trimmed Rocky 9 runtime (`/usr/share/locale` alone is 41 MB).

## 2026-11-02: Pass The Phase 3 Pre-Merge Checks

Request:

- Run the pre-merge checks.

Decision:

- Mark Phase 3 complete. Every acceptance criterion now has evidence, including the bake file's own tags, the plain README build, and the interactive shell.

Affected areas:

- The Phase 3 plan, the roadmap, PLATFORMS.md, and this log. No build input changed.

Validation:

- `docker buildx bake --set '*.platform=<platform>' --load cy2025 cy2026 cy2027` with the bake file's own tags, amd64 first and then arm64. Every step came from cache, and the tags `cy2025`, `cy2026`, `latest`, and `cy2027` were applied.
  - `scripts/validate_image.py` passed all 35 checks on all six images under those tags.
  - Each image's layers, creation time, and config match the recorded `cy<year>-<arch>` image exactly. Only the local image ID differs. amd64 was compared through a second cached bake under scratch tags, because the untagged amd64 images had been removed when arm64 took over the tags.
- The README's `docker build -t algernon_vfx/oiio .` built a native arm64 image from cache (`sha256:4e972319…ec92c9`). It has the same layers and config as `cy2026-arm64` and passed all 35 CY2026 checks.
- The README's `docker run -it --entrypoint='bash' algernon_vfx/oiio`, run through a pseudo-terminal, opened a prompt as `algernon` on `/dev/pts/0` in `/home/algernon`. `oiiotool --version` printed 3.1.19.0, and Python imported OIIO 3.1.19.0 and OCIO 2.5.2.
- The local `algernon_vfx/oiio:cy2025`, `cy2026`, `cy2027`, and `latest` tags now point at the arm64 images.

Follow-up:

- Merge `feature/reference-platform-matrix` to `master` when requested.
- Phase 4: the remaining reproducibility items in the CY2026 entry, including the differing image IDs from identical layers.

## 2026-11-02: Retire The CY2021 Recipe

Request:

- Retire the legacy recipe (Phase 3 Step 5).

Decision:

- Remove `legacy/Dockerfile.cy2021` and its `.dockerignore` entry. The file is identical to the root `Dockerfile` at `be6675c`, the commit that verified the Phase 2 baseline, so the recipe stays recoverable from history. The Phase 2 evidence stays in the [build verification plan](plans/02-build-verification.md) and the CY2021 entry below.
- Remove the legacy recipe from the README and the mission's engineering model. Drop the roadmap's list of suspected problems in that recipe; Phase 2 recorded what actually failed.
- No `cy2021-final` Git tag was created.

Affected areas:

- `legacy/Dockerfile.cy2021` (removed), `.dockerignore`, the README, the mission, the Phase 2 and Phase 3 plans, the roadmap, and this log.

Validation:

- No tracked build file references `centos:centos7` or an ASWF image. The only Dockerfile left is the root `Dockerfile`.
- `docker buildx bake` for `cy2026` on `linux/arm64` resolved every step from cache after the `.dockerignore` change. Its layers and creation time match `cy2026-arm64`; the image ID differs only in metadata, as already noted for Phase 4.
- The local `algernon_vfx/oiio:legacy-cy2021-amd64` image was left in place.

Follow-up:

- Before merging: build every year with the bake file's own tags, and rerun the README's plain build and interactive shell.

## 2026-11-02: Document The Platform Support Contract

Request:

- Write `docs/PLATFORMS.md` (Phase 3 Step 4).

Decision:

- Add [PLATFORMS.md](PLATFORMS.md). It covers how to choose a year; the specified and verified versions for CY2025, CY2026, and CY2027; components left out; deviations; why CY2024 is not built; the verified image IDs and sizes; and the annual maintenance procedure.
- Image identity: the images are not published, so the page records local image IDs from the `cy<year>-<arch>` test builds, not registry digests.
- ACES guidance, resolving the earlier follow-ups:
  - CY2025: an external ACES 2.0 config written for OCIO 2.4, set through `OCIO`. Not tested in the image.
  - CY2027: select a built-in ACES 2.0 config by name, for example `OCIO=ocio://cg-config-v4.0.0_aces-v2.0_ocio-v2.5`.
- Rewrite the README's opening as a per-year table linking PLATFORMS.md. Update the mission's outcome statement and engineering model, which still described the ASWF and CentOS 7 recipe.

Affected areas:

- `docs/PLATFORMS.md`, the README, the mission, the Phase 3 plan, the roadmap, and this log.

Validation:

- Documentation links and anchors resolve.
- On the arm64 images: `/opt/vfx` is 146, 140, and 145 MB for CY2025, CY2026, and CY2027; no image has `pip`; and `OCIO=ocio://default` loads `cg-config-v2.2.0_aces-v1.3_ocio-v2.4`, `cg-config-v4.0.0_aces-v2.0_ocio-v2.5`, and `cg-config-v5.0.0_aces-v2.1_ocio-v2.6`.
- On `cy2027-arm64`, `OCIO=ocio://cg-config-v4.0.0_aces-v2.0_ocio-v2.5` and `OCIO=ocio://studio-config-v4.0.0_aces-v2.0_ocio-v2.5` both load, and an ACES2065-1 to ACEScg conversion works in PyOpenColorIO and in `ImageBufAlgo.colorconvert`.

Follow-up:

- Before merging: run the README's plain build and interactive shell, and build with the bake file's own tags.
- Phase 3 Step 5: retire `legacy/`.

## 2026-11-02: Do Not Build CY2024

Request:

- Skip CY2024 and record why.

Decision:

- Build CY2025–CY2027 only, which completes Phase 3 Step 3. No `cy2024` lock, bake target, or size budget is added.
- Why:
  - CY2024's OIIO series is 2.5; ASWF's CY2024 pin is 2.5.19.1, the newest 2.5 release. OIIO 2.5 calls `checked_find_package(Boost REQUIRED VERSION_MIN 1.53)` for `thread`, and for `filesystem` when the standard library is not used. Every image in this project leaves Boost out.
  - Moving CY2024 to OIIO 3.x would remove Boost, but the image would no longer provide the OIIO 2.5 interface that CY2024 software builds against.
  - CY2024 is the first of the four years to leave the support window, on 2028-01-01.
- Inspection before the decision (static, nothing built): OIIO 2.5.19.1, OCIO 2.3.2, and OpenEXR 3.2.12 are the newest releases in their series. OIIO 2.5 is tested with fmt only through 10.2, so CY2024 would also have needed an older fmt than the other years.

Affected areas:

- The README, the Phase 3 and Phase 4 plans, the roadmap, and this log. The Phase 4 CI matrix is now 6 image jobs.

Validation:

- Documentation only; no image was built for CY2024.

Follow-up:

- `docs/PLATFORMS.md` (Phase 3 Step 4) should list CY2024 as unsupported and say why.
- Before merging: run the README's plain build and interactive shell, and build with the bake file's own tags.

## 2026-11-02: Build And Verify CY2025 On Rocky Linux 8

Request:

- Continue Phase 3 Step 3 with CY2025.

Decision:

- CY2025 specifies glibc 2.28, gcc 11.2.1, C++17, Python 3.11, NumPy 1.26, OCIO 2.4, OpenEXR 3.3, Imath 3.1, and ACES 2.0. Build it on the same Rocky Linux 8.10 bases as CY2026, with `gcc-toolset-11` 11.2.1-9.2.
- Lock 19 source archives and 2 wheels in [build/locks/cy2025.json](../build/locks/cy2025.json):
  - Newest patch releases: CPython 3.11.18, NumPy 1.26.4 (`manylinux_2_17` wheels), Imath 3.1.12, OpenEXR 3.3.15, and OCIO 2.4.2.
  - OIIO 3.1.19.0, the same release as CY2026. ASWF's CY2025 pin, 3.1.6.2, is in the same series, and 3.1 accepts OCIO 2.4, OpenEXR 3.3, Imath 3.1, and C++17.
  - OCIO 2.4.2 recommends older helper releases (expat 2.5.0, yaml-cpp 0.7.0, zlib 1.2.13, and minizip-ng 3.0.7). Use CY2026's newer, security-patched releases instead: expat 2.7.2, yaml-cpp 0.8.0, zlib 1.3.1, and minizip-ng 4.0.10. Each meets OCIO 2.4's minimum, and OCIO uses minizip-ng's native API, which 4.x keeps.
  - pybind11 2.13.6, the newest 2.x. OCIO 2.4 recommends 2.12.1 and OIIO 3.1 accepts 2.7 to 3.0.
  - libdeflate 1.18. OpenEXR 3.3 does not vendor libdeflate; with internal deflate it clones this tag at configure time, which `--network=none` blocks. The Dockerfile points CMake's `FETCHCONTENT_SOURCE_DIR_DEFLATE` at the locked source when the lock includes it.
- Validator corrections found by CY2025, with no change in what they protect:
  - Imath 3.1 names its library from its ABI version (`libImath-3_1.so.29.11.0`), so check the series in the library name. `--buildinfo` already checks the exact release.
  - NumPy 1.26's wheel-bundled OpenBLAS finds `libgfortran` only through the extension that loads it, so `ldd` on the bundled library alone reported it missing. Resolve libraries in a `*.libs` directory from their own directory, and exercise NumPy's linear algebra in the version probe.

Affected areas:

- `Dockerfile` (OpenEXR step), `docker-bake.hcl` (target `cy2025`), `build/locks/cy2025.json`, `build/image-size-budgets.json`, `scripts/validate_image.py`, the README, the Phase 3 plan, the roadmap, and this log.

Validation:

- arm64 builds natively in about 4 minutes; amd64 builds under emulation in about 12 minutes. OpenEXR's configure step used the locked libdeflate with no network.
- `scripts/validate_image.py` passed all 35 checks on both images:
  - `cy2025-amd64`: `sha256:19fb8c182f7b2eb2ba40818e2d4469de21bb9dfcb8e8e95d066e968b4bd9af58`, 360,809,384 bytes.
  - `cy2025-arm64`: `sha256:2310be2c93c88cbaf21dc5b0f115c4727a7c9e6fa142ee897ab1be25c2c3668a`, 344,667,356 bytes.
- What the checks confirmed:
  - `oiiotool --buildinfo` reports OIIO 3.1.19.0 with gcc 11.2 and C++17, plus Imath 3.1.12, OCIO 2.4.2, OpenEXR 3.3.15, libjpeg-turbo 3.1.2, PNG 1.6.50, TIFF 4.7.1, zlib 1.3.1, fmt 12.1.0, pybind11 2.13.6, and Python 3.11.18.
  - NumPy is 1.26.4, and the runtime glibc is 2.28.
  - The highest symbol versions required are `GLIBC_2.28` and `GLIBCXX_3.4.22`, within Rocky 8's `GLIBCXX_3.4.25`.
  - Image I/O, `maketx`, the NumPy read and linear algebra, and the OCIO ACES conversion pass. amd64 OIIO builds `sse2` and arm64 builds `neon`.
- ACES: OCIO 2.4's built-in configs are all ACES 1.3; the default is `cg-config-v2.2.0_aces-v1.3_ocio-v2.4`. OCIO 2.4 does provide the ACES 2.0 output transforms (for example `ACES-OUTPUT - ACES2065-1_to_CIE-XYZ-D65 - SDR-100nit-REC709_2.0`), so an external ACES 2.0 config can use them.
- amd64 is 16 MB larger than arm64, mostly NumPy 1.26's bundled x86-64 OpenBLAS. The budgets are about 5% above the measured sizes.
- The OpenEXR step's change invalidated the CY2026 and CY2027 caches, so both were rebuilt for both architectures and passed all 35 checks again at their previous sizes:
  - `cy2026-amd64` `sha256:b91701f9e6f2431ef91f7e6422db14d6691a22198a03967d30431cc9a4effe75`; `cy2026-arm64` `sha256:63d014790cc84283a2b260521abab3fd52449b91919a108a9f08b33bbd6b8a35`.
  - `cy2027-amd64` `sha256:c4f9d81ef5cdef07c08c2a1b7173cbd880d3040a2cff5e3bdd5c2f3d1d737fa8`; `cy2027-arm64` `sha256:2ecc113fb1a0120a4b70210c0982e24d2afbb59e28a6f6532d87f5717f4126fa`.

Follow-up:

- Phase 3 Step 3: CY2024, the only year on OIIO 2.5, with ACES 1.3.
- `docs/PLATFORMS.md` should explain how CY2025 users obtain an ACES 2.0 config.
- Before merging: run the README's plain build and interactive shell, and build with the bake file's own tags.

## 2026-11-02: Build And Verify CY2027 On Rocky Linux 9

Request:

- Continue Phase 3 Step 3 with the next platform year.

Decision:

- Start Step 3 with CY2027. It shares CY2026's compiler and Python, so it isolates the Rocky Linux 9 base and the newer library series.
- Recheck vfxplatform.com on 2026-11-02 (page last modified 2026-10-17). CY2027 is unchanged: glibc 2.34, gcc 14.2, C++20, Python 3.13, NumPy 2.4, OCIO 2.6, OpenEXR 3.5, Imath 3.2, and ACES 2.0.
- Pinned bases: `rockylinux/rockylinux:9.8` (`sha256:81019941…eed00f`) and `9.8-minimal` (`sha256:e1d0a9f5…ff04`). Rocky 9.8 provides `gcc-toolset-14` 14.2.1-13 and CMake 3.31.8. The builder includes Python and `find`, and the minimal image provides the runtime libraries.
- Lock 19 source archives and 2 wheels in [build/locks/cy2027.json](../build/locks/cy2027.json):
  - Newest patch releases: OCIO 2.6.0, OpenEXR 3.5.3, NumPy 2.4.6 (`manylinux_2_28` wheels), and OIIO 3.2.2.0 (ASWF's reference pin is 3.2.1.1). CPython 3.13.18 and Imath 3.2.3 are unchanged.
  - OCIO 2.6's recommended versions: zlib 1.3.2, yaml-cpp 0.9.0, and minizip-ng 4.2.2. pystring 1.1.4, pybind11 3.0.1, and the `sse2neon` commit are unchanged. expat is 2.8.5, one patch newer than the recommended 2.8.4.
  - OIIO 3.2's defaults: libpng 1.6.58, robin-map 1.4.1, and nanobind 2.13.0. fmt, libjpeg-turbo, and libtiff are unchanged.
- OIIO 3.2 builds its Python bindings with nanobind by default and calls pybind11 the legacy backend. Use nanobind, installed from its locked source against the locked robin-map rather than its git submodule. OCIO still uses pybind11.
- Make the Dockerfile serve both years. Releases that do not use the new options ignore them, so each year's own build is unchanged:
  - the nanobind step runs only when the lock includes nanobind, and the OIIO step selects nanobind only when it is installed;
  - add `OPENEXR_FORCE_INTERNAL_ZSTD=ON` (OpenEXR 3.5 adds zstd), `MZ_PPMD=OFF` (new in minizip-ng 4.2), `YAML_CPP_FORMAT_SOURCE=OFF`, and OIIO `ENABLE_zstd=OFF`.
- The validator checks the binding library the lock names: nanobind or pybind11.
- Keep OIIO 3.2's new amd64 default, SSE4.2 (x86-64-v2). OIIO 3.1 used SSE2 under the same flags. Rocky Linux 9 already requires x86-64-v2 hardware, so CY2027 gains no new hardware requirement. The other components still compile for generic x86-64.

Affected areas:

- `Dockerfile`, `docker-bake.hcl` (target `cy2027`), `build/locks/cy2027.json`, `build/image-size-budgets.json`, `scripts/validate_image.py`, the README, the Phase 3 plan, the roadmap, and this log.

Validation:

- arm64 builds natively; amd64 builds under emulation in about 13 minutes. The amd64 strip step stripped 102 ELF files.
- `scripts/validate_image.py` passed all 35 checks on both images:
  - `cy2027-amd64`: `sha256:cd7916a856d32423cc205a12f70b8e1206d21e4cb80503b37014e33cb28447dc`, 422,629,705 bytes.
  - `cy2027-arm64`: `sha256:ed1aef13e2d1c322632de80a735d8d83d7022415a869a2ef69f95a60aee12f62`, 437,070,594 bytes.
- What the checks confirmed:
  - `oiiotool --buildinfo` reports OIIO 3.2.2.0 with gcc 14.2 and C++20, plus Imath 3.2.3, OCIO 2.6.0, OpenEXR 3.5.3, libjpeg-turbo 3.1.2, PNG 1.6.58, TIFF 4.7.1, zlib 1.3.2, fmt 12.1.0, nanobind 2.13.0, and Python 3.13.18.
  - NumPy is 2.4.6, and the runtime glibc is 2.34.
  - The highest symbol versions required are `GLIBC_2.34` and `GLIBCXX_3.4.29`. `GLIBCXX_3.4.29` is the most Rocky 9's `libstdc++` provides, so CY2027 has no headroom on that check.
  - Every ELF file resolves its libraries, and no excluded libraries are present.
  - Image I/O, `maketx`, the NumPy read, and the OCIO ACES conversion pass.
- OCIO 2.6's default built-in config is `cg-config-v5.0.0_aces-v2.1_ocio-v2.6` (ACES 2.1). The ACES 2.0 configs CY2027 specifies, `cg-config-v4.0.0_aces-v2.0_ocio-v2.5` and `studio-config-v4.0.0_aces-v2.0_ocio-v2.5`, are still built in and load by name.
- The images are about 100 MB larger than CY2026. `/opt/vfx` grew only from 140 MB to 145 MB. The rest is the base: Rocky 9.8 minimal is 242 MB with 121 packages, against 147 MB with 95 packages for Rocky 8.10 minimal. The budgets are about 5% above the measured sizes.
- CY2026 rebuilt with the shared Dockerfile changes (arm64 in 160 s, amd64 in 375 s, from cache up to OpenEXR) and passed all 35 checks again at the same sizes:
  - `cy2026-amd64`: `sha256:56458cadbf4334e67d067fc93fef65df42af14f13225917d6d47b09329274f30`, 332,072,890 bytes.
  - `cy2026-arm64`: `sha256:0753e4bcc289be59a238db762f22025aa1e51aedd044eea608deb8106213bacd`, 335,312,937 bytes.

Follow-up:

- Phase 3 Step 3: CY2024 and CY2025, with `gcc-toolset-11` and C++17.
- Decide whether `docs/PLATFORMS.md` should point CY2027 users at the ACES 2.0 built-in config by name.
- For Phase 4:
  - CPU baseline: amd64 CY2027 OIIO targets x86-64-v2, while CY2026 OIIO targets SSE2.
  - OCIO's NEON path on arm64 is still not enabled.

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
