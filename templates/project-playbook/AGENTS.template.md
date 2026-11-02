# Agent Guidance

Read these project sources before changing code:

- `[MISSION_PATH]` for project goals and durable principles.
- `[ROADMAP_PATH]` for current direction and active plans.
- The plan relevant to the requested work.
- `[GIT_POLICY_PATH]` for branch, worktree, and commit conventions.
- `[IMPLEMENTATION_LOG_PATH]` for recent decisions and validation history.
- `[BACKLOG_PATH]` when the request relates to the general backlog.

## Working Loop

1. Inspect relevant code, tests, docs, and the Git worktree.
2. Follow the active plan and preserve existing changes.
3. Make the smallest coherent change that satisfies the request.
4. Run focused validation; broaden it when shared behavior is affected.
5. Update the implementation log when a meaningful project decision or behavior
   changes.
6. Summarize the changes, validation, and any remaining limitations.

## Project Contracts

- `[PROJECT_SPECIFIC_CONTRACT_1]`
- `[PROJECT_SPECIFIC_CONTRACT_2]`
- `[TESTING_OR_DEPLOYMENT_BOUNDARY]`

When a request conflicts with a documented contract, identify the conflict and
resolve it before changing that contract.
