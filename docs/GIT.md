# Git Workflow

This document defines Git conventions for oiio-docker.

The primary branch is `master` and tracks `origin/master` on GitHub (`mileslauridsen/oiio-docker`). No local `origin/HEAD` reference is set. The older local branches `aswf-test`, `ffmpeg_py27`, `py3env`, and `scratch` are not part of current work; leave them alone unless a task concerns them.

## Branch Naming

Use short, lowercase, hyphenated task names with these prefixes:

- `feature/`: new behavior or capabilities in the image.
- `hotfix/`: urgent fixes to an established working image.
- `planning/`: project direction and design work.
- `docs/`: documentation-only work.
- `maintenance/`: base image, dependency, build, and tooling maintenance.

Examples: `docs/project-playbook`, `maintenance/verify-oiio-build`.

## Branch Creation And Worktree Safety

Create a focused branch before a new task group when starting from a clean worktree:

```sh
git switch -c maintenance/verify-oiio-build
```

For a dirty worktree, inspect staged and unstaged changes before deciding how to isolate new work. Preserve existing edits and staging; do not automatically stash, reset, or carry unrelated changes into a commit. The initial playbook adoption started on the existing `master` checkout because the templates were already staged there.

The untracked `.idea/` directory is local IDE state. Do not commit it.

Keep each branch focused on one task group. Inspect the actual staged diff before committing. Do not commit or push as a side effect of a documentation or implementation request unless requested.

## Commit Signing

Repository policy: signed commits are required, matching the effective `commit.gpgsign=true` setting from the user's global Git configuration observed during setup. Signing has not been tested in this repository.

Resolve signing failures before committing. An unsigned exception requires an authorized maintainer's explicit approval for that commit.

## Documentation And Change Records

Update [IMPLEMENTATION.md](IMPLEMENTATION.md) when a change affects direction, architecture, runtime behavior, dependencies, validation, deployment, or feature scope. Correcting a typo or link alone does not require an entry.

Update the relevant phase plan and roadmap when scope or phase status changes. Retain completed plans as history.

## Before Finishing

- Review the diff and preserve unrelated changes and staging.
- Run the checks appropriate to the change and record what actually ran.
- Report the branch, commit or review state, and remaining limitations.
