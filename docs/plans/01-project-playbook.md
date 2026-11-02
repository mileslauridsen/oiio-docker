# Plan: Project Playbook

## Goal

Give maintainers and agents a project-specific entry point, working conventions, and an evidence-based plan for further development.

## Current State

- The repository contains a two-stage Dockerfile, brief usage instructions, an MIT license, and reusable playbook templates.
- At adoption, the templates were already staged on `master`, and `.idea/` was untracked. No other edits were present.

## Decisions And Boundaries

- Adopt the templates into a root `AGENTS.md` and `docs/`, keeping the reusable originals.
- Follow the document layout already adopted in the sibling ffmpeg-docker repository.
- Document the existing recipe separately from future verification and improvements.
- Preserve the staged templates and the untracked IDE directory. This phase changes documentation only.
- Use signed commits for future commits, consistent with the effective Git configuration. Create no commit during setup.

## Work Plan

### 1. Establish Project Documents

- Add agent guidance, a mission, a Git policy, a roadmap, phase plans, and an implementation log.
- Replace the template prompts with repository-specific facts and explicit unknowns.

### 2. Connect And Validate

- Link the project documents from the README, and link the plans from the roadmap.
- Check local Markdown links, unresolved template prompts, and whitespace errors in the changed documents.
- Review Git status and confirm that the staged templates are preserved.

## Validation

- Inspect the Dockerfile, README, templates, and effective commit-signing configuration.
- Run local documentation link and placeholder checks and `git diff --check`.
- This documentation-only adoption needs no image build or runtime test.

## Acceptance Criteria

- All six playbook document types are adopted with project-specific content.
- The agent guidance and the README lead to the relevant project documents.
- Build verification is documented as planned work, with runnable checks and observable acceptance criteria.
- Existing user changes and staging are preserved.

## Status

Status: complete

Last updated: 2026-11-01
