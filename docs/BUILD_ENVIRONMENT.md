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

## Reproducible Builds

Two builds of the same year and architecture from the same inputs produce the same image, down to the image ID. The Dockerfile makes them so:

- **Fixed build time:** `SOURCE_DATE_EPOCH=0` is set in every build step, and `docker-bake.hcl` also passes it to BuildKit. Compilers use it for `__DATE__` and `__TIME__`, CMake for `string(TIMESTAMP)`, and BuildKit for the image's creation time and history. So `sys.version` reports CPython's build date as `Jan  1 1970, 00:00:00`, libjpeg-turbo reports build `19700101`, and `docker image inspect` shows the image as created on 1970-01-01. `validate_lock.py` requires the value in both files.
- **Locale, time zone, and paths:** the builder runs with `LC_ALL=C`, `LANG=C`, and `TZ=UTC`. Every source builds under its fixed `/src/<name>` path.
- **Python bytecode:** the last compile step deletes every `__pycache__` and recompiles CPython's standard library, NumPy, and the other Python files with `compileall --invalidation-mode checked-hash`. A checked-hash `.pyc` records its source's hash instead of its modification time. `-B` keeps the interpreter from writing timestamp-based bytecode for the modules `compileall` itself imports, and `-f` recompiles those.
- **File times:** every path under `/opt/vfx` is set to `SOURCE_DATE_EPOCH`. The runtime stage copies `/opt/vfx` through a bind mount in the same step that creates the `algernon` user, then resets the times of what that step changed: `/opt`, `/etc`, `/etc/passwd`, `/etc/group`, `/home`, and `/home/algernon`. A `COPY` would have left `/opt` with the build time in its own layer. That step runs with `HOME` on a tmpfs, because Rosetta, when Docker Desktop emulates amd64, writes its cache under `$HOME/.cache` and would otherwise add `/root/.cache` to the layer with the build time.

`scripts/reproducible_build.py` checks this. It copies the repository into two new directories, builds the year from each with `--no-cache --pull` on the pinned builder, and compares:

- the SHA-256 of every ELF file under `/opt/vfx` (executables, shared libraries, Python extensions) and of every system library they load;
- the whole root filesystem from `docker export`: each file's content, mode, owner, and modification time, and each directory and link. It skips the paths Docker creates in every container and `/etc`'s own time, which `docker export` changes;
- separately, the layer diff IDs, the config digest, and the local image ID.

It exits non-zero if the binaries or the filesystem differ, and reports the image identity either way:

```sh
python3 scripts/reproducible_build.py --year cy2026 --platform linux/arm64 --work-dir /path/to/new-directory --metadata repro.json
```

On an Apple silicon host, a pair of cold builds and its comparison take about 10 minutes on arm64 and about 30 minutes for amd64 under emulation. `--baseline-image` reuses an earlier cold build as the first of the pair.

## Validation

Check the locks, package lists, CPU baselines, build tools, and CI workflow pins without building:

```sh
python3 scripts/validate_lock.py
```

A build checks its own inputs: the fetch stage verifies every source, and the builder stage verifies its RPM set. After a build, `scripts/validate_image.py` checks the image, including its runtime RPM set.

## Continuous Integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs these checks on GitHub-hosted runners: `ubuntu-24.04` for amd64 and `ubuntu-24.04-arm` for arm64, so both architectures build natively. It runs on pull requests, on pushes to `master`, every Monday at 07:41 UTC, and on manual runs, with read-only access to the repository.

- **`lock-validation`** runs `validate_lock.py` and compiles every script to check its syntax. The other jobs wait for it.
- **`image-validation`**, on every run except the weekly one, builds each year on each architecture: six jobs that do not cancel each other when one fails. Each job builds with `docker buildx bake` on the pinned BuildKit, then runs `validate_image.py` and `smoke_images.py`. It uploads an `oiio-build-<year>-<arch>` artifact with the year's lock, the build tools, the size budgets, the architecture's RPM lists, the Buildx metadata, both checks' JSON results, `docker image inspect` and `docker history` output, and a `SHA256SUMS` of those files.
- **`cold-reproducibility`**, on the weekly and manual runs only, runs `reproducible_build.py` for the same six combinations and uploads its report and both build logs as `oiio-reproducibility-<year>-<arch>`.

Every action is pinned by full commit SHA, and `build/docker-build-tools.json` records those commits, the Buildx version (`v0.38.1`), and the runners. `validate_lock.py` fails if the workflow uses an action, Buildx version, BuildKit image, or runner that file does not record, if its year matrix differs from the locks, or if it asks for more than `contents: read`.

| Action | Version | Commit |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `docker/setup-buildx-action` | v4.4.1 | `f87e5991a6d7451dcb8d9637bfbc97413f497069` |
| `actions/upload-artifact` | v4.6.2 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |

Every image job builds cold from the locked inputs, without a layer cache. The first hosted run took 12–21 minutes per image job, with the six running in parallel; the image jobs time out after 60 minutes and the cold-reproducibility jobs, which build twice, after 120. A GitHub Actions cache was tried first and never activated: Buildx skips a `type=gha` cache, without a warning, unless the job's cache token is in its environment, which Docker's own build actions provide and a `run:` step does not. A working cache would have needed one more action, or that token exposed to every later step, and about 6 GB of the repository's 10 GB cache limit for each branch, for a few minutes saved on a public repository whose minutes are free.

A local image ID depends on Docker's image store: the runners' classic store uses the config digest, and the containerd image store, which Docker Desktop uses here, uses the manifest digest. The config digest is the same in both, so compare a hosted build with a local one by config digest, which [PLATFORMS.md](PLATFORMS.md#verified-images) lists. The first hosted run's six config digests matched the local ones.
