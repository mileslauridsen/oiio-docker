# Mission

Provide a containerized OpenImageIO (OIIO) and OpenColorIO (OCIO) environment so that visual effects artists and pipeline developers can inspect, convert, color-manage, and prepare texture images. They should be able to do this from the command line or from Python, without building the VFX library stack on every workstation or render worker.

The intended outcome is one image per supported VFX Reference Platform year whose tool set, library versions, build inputs, and runtime behavior are documented and verified. The CY2025, CY2026, and CY2027 images build and pass their checks on amd64 and arm64; [PLATFORMS.md](PLATFORMS.md) is their support contract.

## Development Loop

```text
define tool and format requirements -> update build recipe -> build image -> verify tools, Python bindings, and image I/O -> document operation -> repeat
```

- Keep usage simple: build an image, then run OIIO tools or Python against mounted images.
- Align library versions with a named [VFX Reference Platform](https://vfxplatform.com/) year, and record any departure from it.
- Make dependency versions and validation evidence traceable. Pin source revisions and base images rather than building from moving branches.
- Keep compilers, source trees, and build-only dependencies out of the final runtime stage.
- Record failures with the failing build step or command and enough environment details to reproduce them.

## Engineering Model

- `Dockerfile`: one parameterized recipe for every platform year.
  - The builder stage uses a digest-pinned Rocky Linux base and its `gcc-toolset` compiler. It fetches only locked sources, wheels, and tools, checking each SHA-256 and every published GPG or Sigstore signature, then builds CPython, NumPy, Imath, OpenEXR, OCIO, OIIO, and their image libraries into `/opt/vfx` with network access disabled.
  - The runtime stage is the matching Rocky Linux minimal base plus `/opt/vfx`, and runs as the non-root user `algernon`.
- `build/locks/cy<year>.json`: each year's specified versions, toolchain, and locked inputs. `build/fetch_sources.py` downloads and verifies them with the keys in `build/keys/`, and `scripts/validate_lock.py` checks the locks ([SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md)). `build/rpm/<year>/` holds each year's pinned Rocky repositories and exact RPM sets, which `build/verify_rpm_lock.py` enforces in the build ([BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md)).
- `docker-bake.hcl`: one target per year, with that year's base images, compiler, and C++ standard.
- `scripts/validate_image.py` and `build/image-size-budgets.json`: check a built image against its lock and size budget: versions, symbol limits, linkage, contents, licenses, and size.
- `scripts/reproducible_build.py`: builds a year twice from isolated copies without cache and compares the shipped binaries, the root filesystem, and the image identity ([BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md#reproducible-builds)).
- `scripts/collect_licenses.py`: copies the license and notice files of every shipped component into `/opt/vfx/share/licenses` during the build ([SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md#shipped-licenses)).
- `build/image-support.json`, `scripts/generate_test_images.py`, and `scripts/smoke_images.py`: the image support contract, its independently generated fixtures, and the checks that run it against a built image ([IMAGE_SUPPORT.md](IMAGE_SUPPORT.md)).
- `README.md`: the operator entry point, with build and interactive-shell commands and documentation links.
- `docs/`: mission, platform support contract ([PLATFORMS.md](PLATFORMS.md)), direction, execution plans, Git policy, and decision history.
- `templates/project-playbook/`: reusable source templates, kept separate from the adopted project documents.

Images enter and leave through caller-supplied mounts. This repository does not implement an application server, job scheduler, or automated image pipeline.

## Quality Bar

- Keep the `algernon_vfx/oiio` image tag and the interactive Bash entry point used in the README unless they are deliberately revised.
- Preserve the non-root runtime user unless a plan records a reason to change it.
- Validate Dockerfile changes with all of the following, and record the platform and image identity with the results:
  - an image build;
  - `oiiotool`, `iinfo`, and `maketx` startup checks;
  - an `OpenImageIO` and `PyOpenColorIO` Python import;
  - a round trip that writes and reads an OpenEXR image on a mounted volume.
- Do not claim that the image builds, that the runtime stage links correctly, or that the Python bindings import without evidence.
