# Roadmap

This is the high-level direction for oiio-docker. Detailed execution belongs in the linked plans; recorded decisions belong in [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Planning Index

- [Phase 1: Project playbook](plans/01-project-playbook.md): establish project orientation, workflow, and planning documents.
- [Phase 2: Build verification](plans/02-build-verification.md): record whether the legacy CY2021 recipe builds and runs, and establish the validation checks that later phases reuse.
- [Phase 3: Reference platform build matrix](plans/03-reference-platform-matrix.md): build and verify one small image per supported VFX Reference Platform year (CY2024–CY2027) from clean Rocky Linux bases, then retire the CY2021 recipe.

## Current Direction

- The project playbook is adopted. Next comes Phase 2: measure the existing recipe and establish the validation checks. Phase 3 then replaces the single CY2021 image with a matrix aligned to the VFX Reference Platform support window.
- Static inspection of the recipe points to several likely problems; none has been demonstrated by a build:
  - The runtime base `centos:centos7` reached end of life in June 2024, and its package mirrors moved to vault.
  - OIIO is cloned from its moving default branch with no pinned release.
  - The pybind11 path refers to `/home/python_user`, a user the Dockerfile never creates.
  - The runtime stage copies whole system directories across distributions. This may fail to place Python modules or shared libraries where the runtime expects them.
- Phase 3 covers the modernization. It does not use ASWF build images. Each year builds from a digest-pinned Rocky Linux base at that year's glibc floor, with Rocky's `gcc-toolset` compiler and checksum-verified upstream sources for the components the platform specifies. Runtime stages contain only what OIIO's tools and Python bindings need.
- Keep the two-stage build model, the direct OIIO CLI workflow, and Python access.
- Track further work in the phase plans rather than in a duplicate backlog.

## Development Loops

```text
documentation: inspect repository -> update project documents -> check links and consistency
build: define compatibility -> inspect dependencies -> build -> inspect tools and Python bindings -> read and write images -> record evidence
```

## Phase Status

| Phase | Status | Plan | Outcome |
| --- | --- | --- | --- |
| 1. Project playbook | complete | [Plan](plans/01-project-playbook.md) | Project guidance, workflow, mission, roadmap, plans, and log adopted. |
| 2. Build verification | planned | [Plan](plans/02-build-verification.md) | A recorded legacy baseline and reusable build and runtime checks. |
| 3. Reference platform build matrix | planned | [Plan](plans/03-reference-platform-matrix.md) | Small, verified `cy2024`–`cy2027` images on Rocky Linux for amd64 and arm64, matching each year's platform versions; CY2021 recipe retired. |

## Assumptions

- The image is built and used locally. This setup configures no registry publication or release automation.
- Phase 3 targets `linux/amd64` and `linux/arm64`. The development host is an Apple M5 Pro with an arm64 Docker engine, so arm64 builds run natively and amd64 builds run under emulation.
- Rocky Linux 8.10 and 9.8 provide the specified glibc and gcc versions. Python 3.13 and the specified NumPy versions are not packaged there, so they come from pinned sources and wheels.
- OIIO is not part of the VFX Reference Platform specification. The starting OIIO pins are the releases ASWF chose for each year, used as a known-compatible reference.
