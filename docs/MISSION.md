# Mission

Provide a containerized OpenImageIO (OIIO) and OpenColorIO (OCIO) environment so that visual effects artists and pipeline developers can inspect, convert, color-manage, and prepare texture images. They should be able to do this from the command line or from Python, without building the VFX library stack on every workstation or render worker.

The intended outcome is an image whose tool set, library versions, build inputs, and runtime behavior are documented and verified. Neither has happened yet. The current recipe dates from April 2021 and has not been built since this documentation was adopted. See the [build verification plan](plans/02-build-verification.md).

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

- `Dockerfile`: has two stages.
  - The compile stage is based on `aswf/ci-vfxall:2021-clang10.5`. It supplies OCIO, OpenEXR, and the rest of the CY2021 library stack. On top of that it installs pybind11, clones OIIO from GitHub, and builds OIIO with its command-line tools and Python bindings.
  - The runtime stage is based on `centos:centos7`. It copies system and `/usr/local` directories from the compile stage, plus the OIIO build's `bin` directory, and runs as the non-root user `algernon`.
- `README.md`: the operator entry point, with build and interactive-shell commands and documentation links.
- `docs/`: mission, direction, execution plans, Git policy, and decision history.
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
