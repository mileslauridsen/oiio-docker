# Implementation Log

Record decisions that change project direction, specifications, runtime behavior, tests, validation, dependencies, deployment, or architecture. Link to plans rather than duplicating their details.

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
