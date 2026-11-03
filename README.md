# oiio-docker
Installation of OIIO and OCIO for use in a VFX pipeline, built to match the [VFX Reference Platform](https://vfxplatform.com/#reference-platform).

There is one image per platform year, each built for `linux/amd64` and `linux/arm64`:

| Image | Platform year | Base (glibc) | Compiler | Python / NumPy | OCIO / OpenEXR / Imath | OIIO |
| --- | --- | --- | --- | --- | --- | --- |
| `algernon_vfx/oiio:cy2025` | CY2025 | Rocky Linux 8 (2.28) | gcc 11.2, C++17 | 3.11 / 1.26 | 2.4 / 3.3 / 3.1 | 3.1 |
| `algernon_vfx/oiio:cy2026`, `latest` | CY2026 (current) | Rocky Linux 8 (2.28) | gcc 14.2, C++20 | 3.13 / 2.3 | 2.5 / 3.4 / 3.2 | 3.1 |
| `algernon_vfx/oiio:cy2027` | CY2027 (from 2027-01-01) | Rocky Linux 9 (2.34) | gcc 14.2, C++20 | 3.13 / 2.4 | 2.6 / 3.5 / 3.2 | 3.2 |

Choose the year your DCCs and plugins target. [docs/PLATFORMS.md](docs/PLATFORMS.md) lists each image's exact versions, the components left out, deviations from the platform (including ACES), and the verified image IDs and sizes. Versions and checksums are locked in [build/locks/](build/locks/).

There is no **CY2024** image. CY2024's OpenImageIO series, 2.5, requires Boost, which these images leave out, and moving it to OpenImageIO 3 would break compatibility with software built against 2.5.

## Building with docker
Build the current year (CY2026) for the Docker engine's own platform:

```docker build -t algernon_vfx/oiio .```

Build one year for one platform with the bake file:

```docker buildx bake --set '*.platform=linux/arm64' --load cy2026```

Replace `cy2026` with `cy2025` or `cy2027` for another year (`cy2026` is also tagged `latest`). Use `linux/amd64` for the x86-64 image. On an arm64 host such as Apple silicon, it builds under emulation.

## Running image in an interactive bash shell
```docker run -it --entrypoint='bash' algernon_vfx/oiio```

Add `:cy2025` or another year's tag to choose a year, and `-v "$PWD:/work" -w /work` to work on images in the current directory.

## Validating an image
```python3 scripts/validate_image.py --image algernon_vfx/oiio:cy2026 --platform linux/arm64 --year cy2026```

The validator checks the image against its lock. It covers:

- tool, library, and Python versions;
- the glibc and `libstdc++` symbol limits;
- unresolved libraries and excluded components;
- EXR, TIFF, PNG, and JPEG round trips, `maketx`, and NumPy reads;
- an OCIO ACES conversion;
- the unpacked size against the budget in [build/image-size-budgets.json](build/image-size-budgets.json).

## Project documentation

- [Platforms](docs/PLATFORMS.md): the supported years, their verified versions, and annual maintenance.
- [Mission](docs/MISSION.md): purpose, architecture, and quality expectations.
- [Roadmap](docs/ROADMAP.md): phase status and the next planned work.
- [Git workflow](docs/GIT.md): branches, worktree safety, and signed commits.
- [Implementation log](docs/IMPLEMENTATION.md): decisions and validation history.
