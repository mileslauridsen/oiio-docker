# Roadmap

This is the high-level direction for oiio-docker. Detailed execution belongs in the linked plans; recorded decisions belong in [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Planning Index

- [Phase 1: Project playbook](plans/01-project-playbook.md): establish project orientation, workflow, and planning documents.
- [Phase 2: Build verification](plans/02-build-verification.md): establish whether the existing image builds and runs, then fix the failures that are demonstrated.

## Current Direction

- The project playbook is adopted. Next comes Phase 2: measure the existing recipe before modernizing it.
- Static inspection of the recipe points to several likely problems; none has been demonstrated by a build:
  - The runtime base `centos:centos7` reached end of life in June 2024, and its package mirrors moved to vault.
  - OIIO is cloned from its moving default branch with no pinned release.
  - The pybind11 path refers to `/home/python_user`, a user the Dockerfile never creates.
  - The runtime stage copies whole system directories across distributions. This may fail to place Python modules or shared libraries where the runtime expects them.
- Use the Phase 2 evidence to define a modernization phase. Candidate work for that phase:
  - pick a current ASWF base and VFX Reference Platform year;
  - pin the OIIO release and the base image digests;
  - replace the CentOS 7 runtime;
  - copy only the runtime artifacts the image needs.
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
| 2. Build verification | planned | [Plan](plans/02-build-verification.md) | A recorded build and runtime baseline, plus focused fixes for demonstrated failures. |

## Assumptions

- The image is built and used locally. This setup configures no registry publication or release automation.
- The target platform has not been chosen. The ASWF CI images are published for `linux/amd64`. The development host is macOS, so its architecture and Docker engine need to be recorded in Phase 2.
- The compile stage relies on OCIO and the other libraries in the ASWF CY2021 image rather than building them from source.
