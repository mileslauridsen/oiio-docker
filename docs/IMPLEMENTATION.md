# Implementation Log

Record decisions that change project direction, specifications, runtime behavior, tests, validation, dependencies, deployment, or architecture. Link to plans rather than duplicating their details.

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
