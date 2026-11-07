# Build Environment Lock

This document records the fixed build environment for each platform year and architecture. The sources are covered in [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md). The machine running Docker never selects compiler options.

Each year's lock, `build/locks/cy<year>.json`, holds that year's environment in its `toolchain` section. `build/docker-build-tools.json` records the Docker build tools shared by every year.

## Base Images

Every base image is pinned by its multi-platform index digest in the lock and `docker-bake.hcl`. The lock also records the per-architecture manifest digest each index selects.

| Image | Years | Index digest | amd64 manifest | arm64 manifest |
| --- | --- | --- | --- | --- |
| `rockylinux/rockylinux:8.10` | CY2025, CY2026 builder | `sha256:e8a49c54…` | `sha256:f5529992…` | `sha256:f5147655…` |
| `rockylinux/rockylinux:8.10-minimal` | CY2025, CY2026 runtime | `sha256:6d2ede10…` | `sha256:af5fbd46…` | `sha256:55ddcbe1…` |
| `rockylinux/rockylinux:9.8` | CY2027 builder | `sha256:81019941…` | `sha256:ed654c69…` | `sha256:67492e5a…` |
| `rockylinux/rockylinux:9.8-minimal` | CY2027 runtime | `sha256:e1d0a9f5…` | `sha256:8c5ffaa8…` | `sha256:e6776253…` |

## RPM Packages

Rocky Linux has no dated snapshot service like Debian's. It does keep every superseded build within a minor release: on 2026-11-05, Rocky 8.10's BaseOS offered seven builds of `openssl-devel`, from `1.1.1k-12.el8_9` to `1.1.1k-18.el8_10`. When a minor release is retired, its tree moves from `pub` to `vault`. On 2026-11-05, `https://dl.rockylinux.org/pub/rocky/9.7/` held only a README, while `/vault/rocky/9.7/` served the full repositories. Neither 8.10 nor 9.8 was in the vault yet.

So the builder installs exact package versions from its own minor release only:

- `build/rpm/<year>/rocky.repo` names Rocky's BaseOS and AppStream repositories for that minor release, at `https://dl.rockylinux.org/pub/rocky/<minor>/` first and `https://dl.rockylinux.org/vault/rocky/<minor>/` second. dnf tries the second URL when the first fails, so the lock keeps installing after the release is retired. No mirror list is used, and dnf checks every package's Rocky signature (`gpgcheck=1`).
- `builder-<arch>.packages` lists every package the install adds or upgrades, by exact name, epoch, version, release, and architecture. The Dockerfile passes the whole list to `dnf install` with weak dependencies off, so dnf has nothing left to choose.
- `resolved-<arch>.packages` lists every RPM installed in the builder afterwards, including the base image's own packages and the imported Rocky key. `build/verify_rpm_lock.py` runs in the same build step and fails the build if the installed set differs at all.
- `runtime-<arch>.packages` lists the runtime base image's RPMs. The runtime stage installs none, and `scripts/validate_image.py` checks that the image's set matches.
- The Dockerfile runs no `dnf update`; `scripts/validate_lock.py` rejects one.

Package counts:

| Year | Requested | Installed by the builder (amd64 / arm64) | Builder total | Runtime total |
| --- | --- | --- | --- | --- |
| CY2025 | 12 | 63 / 63 | 209 | 95 |
| CY2026 | 12 | 65 / 65 | 211 | 95 |
| CY2027 | 12 | 54 / 53 | 196 | 121 |

The architectures differ only by Rocky's own architecture-specific packages: CY2027 installs `glibc-headers` on x86_64 only, and its arm64 base image already carries `libatomic`. The Rocky 8 builds upgrade three base packages (`openssl-libs`, `bzip2-libs`, and `tar`); those upgrades are part of the lock.

The `gcc-toolset` runtime package's install script prints `ValueError: SELinux policy is not managed or store cannot be accessed.` A container has no SELinux policy store; the install completes and the RPM check passes.

### Updating The Package Lock

The requested packages are listed in each lock's `toolchain.rpm.requested`. To refresh a year's closure, for example after a security update or a new requested package:

```sh
python3 scripts/resolve_rpm_lock.py --year cy2026 --platform linux/amd64
python3 scripts/resolve_rpm_lock.py --year cy2026 --platform linux/arm64
```

The script installs the requested packages in the locked builder image through the year's repo file and rewrites the three package lists. Review the diff, update the lock's `toolchain.tools` if a tool changed, run `python3 scripts/validate_lock.py`, and rebuild the year on both architectures.

## Toolchain

The builder uses Rocky's `gcc-toolset` compiler and binutils, not the base system's. Versions are from the resolved package lists and are the same on both architectures:

| Year | gcc and g++ | binutils | CMake | Make | glibc |
| --- | --- | --- | --- | --- | --- |
| CY2025 | `gcc-toolset-11` 11.2.1-9.2.el8_9 | 2.36.1-4.el8_9 | 3.26.5-2.el8 | 4.2.1-11.el8 | 2.28-251.el8_10.2 |
| CY2026 | `gcc-toolset-14` 14.2.1-11.el8_10 | 2.41-4.el8_10.1 | 3.26.5-2.el8 | 4.2.1-11.el8 | 2.28-251.el8_10.2 |
| CY2027 | `gcc-toolset-14` 14.2.1-13.el9 | 2.41-6.el9 | 3.31.8-3.el9 | 4.3-8.el9 | 2.34-266.el9_8 |

The builds use CMake's Unix Makefiles generator; Ninja is not installed.

## CPU Baselines

The `vfx-gcc` and `vfx-g++` wrappers add the year's flags to every compile:

| Year | linux/amd64 | linux/arm64 |
| --- | --- | --- |
| CY2025, CY2026 | `-march=x86-64 -mtune=generic` (x86-64-v1) | `-march=armv8-a -mtune=generic` |
| CY2027 | `-march=x86-64-v2 -mtune=generic` | `-march=armv8-a -mtune=generic` |

- Rocky 8 runs on x86-64-v1 hardware, so CY2025 and CY2026 keep the most portable baseline.
- Rocky 9 itself requires x86-64-v2, so the CY2027 image could never run on an older CPU. Compiling for x86-64-v2 loses no hardware and lets the compiler use SSE4.2 and POPCNT.
- OIIO is configured with an empty `USE_SIMD`, so it adds no SIMD flags of its own: the `-march` baseline alone sets its instruction set. OIIO 3.1's default is already empty. OIIO 3.2 would otherwise add `-msse4.2` to its own code only; with x86-64-v2 everywhere, CY2027's OIIO reports the same features as before (`sse2,sse3,ssse3,sse41,sse42`), and the other libraries and CPython now use them too. `oiiotool --buildinfo` reports the result, and `validate_image.py` prints it.
- `docker-bake.hcl` sets `AMD64_MARCH` per year; `validate_lock.py` checks it against the lock's `toolchain.cpu_baselines`.

Confirm these baselines against the production workers before raising them.

## Docker Build Tools

- Dockerfile frontend: `docker/dockerfile:1.7.1`, pinned in the Dockerfile's syntax line to index digest `sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e`. `validate_lock.py` checks the line against `build/docker-build-tools.json`.
- BuildKit: `moby/buildkit:v0.33.1`, pinned to index digest `sha256:cec9f139f45e93c5c69c60f8b07cfad9f43f4ef6b6a6cd917527fea5ff2e3dea`. Both match ffmpeg-docker.
- Observed locally: Buildx `v0.38.1` and Docker Engine `29.9.2`. Docker Desktop's built-in builder runs BuildKit `v0.34.0`, so use the pinned builder instead.

Create the pinned builder once:

```sh
docker buildx create --name oiio-pinned --driver docker-container \
  --driver-opt image=moby/buildkit:v0.33.1@sha256:cec9f139f45e93c5c69c60f8b07cfad9f43f4ef6b6a6cd917527fea5ff2e3dea
docker buildx inspect oiio-pinned --bootstrap
```

Build one year and platform with it. `--load` imports the image into the local Docker image store:

```sh
docker buildx bake --builder oiio-pinned --set '*.platform=linux/arm64' --load cy2026
```

Build one year at a time: three years in parallel on an 8 GB Docker VM ran out of memory.

## Validation

Check the locks, package lists, CPU baselines, and build tools without building:

```sh
python3 scripts/validate_lock.py
```

A build checks its own inputs: the fetch stage verifies every source, and the builder stage verifies its RPM set. After a build, `scripts/validate_image.py` checks the image, including its runtime RPM set.
