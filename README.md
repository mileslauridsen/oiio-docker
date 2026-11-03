# oiio-docker
Installation of OIIO and OCIO for use in a VFX pipeline, built to match the [VFX Reference Platform](https://vfxplatform.com/#reference-platform).

The current image targets **CY2026**:

- Rocky Linux 8 (glibc 2.28), gcc 14.2, and C++20;
- Python 3.13 with NumPy 2.3;
- OpenColorIO 2.5, OpenEXR 3.4, and Imath 3.2;
- OpenImageIO 3.1.

It is built for `linux/amd64` and `linux/arm64`. Versions and checksums are locked in [build/locks/cy2026.json](build/locks/cy2026.json).

A **CY2027** image (`cy2027`, effective 2027-01-01) is also available. It uses Rocky Linux 9 (glibc 2.34), gcc 14.2 with C++20, Python 3.13 with NumPy 2.4, OpenColorIO 2.6, OpenEXR 3.5, Imath 3.2, and OpenImageIO 3.2. Its lock is [build/locks/cy2027.json](build/locks/cy2027.json).

A **CY2025** image (`cy2025`) is also available. It uses Rocky Linux 8 (glibc 2.28), gcc 11.2 with C++17, Python 3.11 with NumPy 1.26, OpenColorIO 2.4, OpenEXR 3.3, Imath 3.1, and OpenImageIO 3.1. Its lock is [build/locks/cy2025.json](build/locks/cy2025.json).

## Building with docker
Build for the Docker engine's own platform:

```docker build -t algernon_vfx/oiio .```

Build one platform explicitly with the bake file (`cy2026` is also tagged `latest`):

```docker buildx bake --set '*.platform=linux/arm64' --load cy2026```

Use `linux/amd64` for the x86-64 image. On an arm64 host such as Apple silicon, it builds under emulation. Replace `cy2026` with `cy2025` or `cy2027` to build another year's image.

## Running image in an interactive bash shell
```docker run -it --entrypoint='bash' algernon_vfx/oiio```

## Validating an image
```python3 scripts/validate_image.py --image algernon_vfx/oiio:cy2026 --platform linux/arm64 --year cy2026```

The validator checks the image against its lock. It covers:

- tool, library, and Python versions;
- the glibc and `libstdc++` symbol limits;
- unresolved libraries and excluded components;
- EXR, TIFF, PNG, and JPEG round trips, `maketx`, and NumPy reads;
- an OCIO ACES conversion;
- the size budget in [build/image-size-budgets.json](build/image-size-budgets.json).

The previous CY2021 recipe remains in [legacy/Dockerfile.cy2021](legacy/Dockerfile.cy2021) until the full platform matrix is verified.

## Project documentation

- [Mission](docs/MISSION.md): purpose, architecture, and quality expectations.
- [Roadmap](docs/ROADMAP.md): phase status and the next planned work.
- [Git workflow](docs/GIT.md): branches, worktree safety, and signed commits.
- [Implementation log](docs/IMPLEMENTATION.md): decisions and validation history.
