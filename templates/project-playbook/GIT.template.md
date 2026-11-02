# Git Workflow

This document defines Git conventions for `[PROJECT_NAME]`. Treat the defaults
below as a starting point: confirm or replace them to match the repository's
branching model, hosting service, and signing requirements.

## Branch Naming

Default feature branch format:

```text
feature/<short-lowercase-hyphenated-name>
```

Choose the prefixes this repository uses:

- `feature/`: [new behavior or feature work]
- `hotfix/`: [urgent production fixes]
- `planning/`: [planning and design work, if used]
- `docs/`: [documentation-only changes, if used]
- `maintenance/`: [maintenance work, if used]

Keep names short and describe the task or behavior. Replace these defaults if
the team uses another convention. Examples for this repository:

- `[branch-name-example]`
- `[branch-name-example]`

## Branch Creation And Worktree Safety

Create a branch before starting a new task group or materially separate piece
of work, unless the repository's normal workflow says otherwise:

```shell
git switch -c [branch-prefix]/<short-task-name>
```

When starting from an uncommitted worktree, preserve existing user and agent
changes. Do not reset, discard, or overwrite unrelated work to create or switch
branches.

Keep each branch focused on one task group. Split work when its scope changes
materially, according to the team's review and release workflow.

## Commit Signing

Repository policy: `[required / recommended / not configured]`.

If signing is required, resolve local signing setup failures before committing.
Allow an unsigned exception only when an authorized maintainer explicitly
approves that one-time exception. If signing is not required, remove this
exception rule and document the actual repository policy.

## Documentation And Change Records

Update `[DECISION_LOG_PATH]` when a change affects project direction, design,
architecture, runtime behavior, tests, validation, data contracts, deployment,
or feature scope. For routine changes, check whether an entry is warranted
under the project's documentation policy.

## Before Finishing

- Confirm the branch contains only work for its intended task group.
- Follow the repository's required review, validation, and commit process.
- Report the commit or review state and any remaining limitations.
