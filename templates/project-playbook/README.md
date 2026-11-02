# Project Playbook Templates

Copyable starting documents for adding project planning and agent orientation
to another software repository. These templates are intentionally project
agnostic; replace the bracketed prompts and remove guidance that does not fit.

## Adopt

1. Copy `AGENTS.template.md` to the repository root as `AGENTS.md`.
2. Copy `GIT.template.md` into the repository's documentation area and decide
   its branch and commit-signing policies.
3. Copy the mission, roadmap, phase plan, and implementation log templates into
   the repository's documentation area, adjusting paths as needed.
4. Fill in the mission, active work, important contracts, and validation
   commands. Keep project-specific facts in the project documents rather than
   repeating them in `AGENTS.md`.
5. Link the active phase plans from the roadmap and have `AGENTS.md` point agents
   to those documents, including the Git policy.
6. Start a dated implementation-log entry when a change affects project
   direction, behavior, tests, validation, deployment, or architecture.

## Files

- `AGENTS.template.md`: agent entry point and work loop.
- `GIT.template.md`: branch, worktree, commit, and documentation conventions.
- `MISSION.template.md`: project purpose and durable principles.
- `ROADMAP.template.md`: direction, phase index, and development loops.
- `PLAN_PHASE.template.md`: scoped work plan and acceptance criteria.
- `IMPLEMENTATION.template.md`: decision and validation history.

Treat the mission, roadmap, active plan, and implementation log as separate
layers: purpose, direction, execution, and recorded decisions. Keep details in
the layer where they are most useful, and link between layers instead of
duplicating them.
