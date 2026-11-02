# Agent Guidance

Read these project sources before changing code:

- [Mission](docs/MISSION.md) for goals, architecture, and durable principles.
- [Roadmap](docs/ROADMAP.md) for current direction and the phase index.
- The phase plan relevant to the requested work.
- [Git workflow](docs/GIT.md) for branch, worktree, and signing conventions.
- [Implementation log](docs/IMPLEMENTATION.md) for decisions and validation history.

## Working Loop

1. Inspect relevant code, documentation, and the Git worktree.
2. Follow the relevant plan and preserve existing staged and unstaged changes.
3. Make the smallest coherent change that satisfies the request.
4. Run focused validation and distinguish static inspection from a successful image build and runtime check.
5. Update the implementation log when direction, behavior, architecture, or validation changes.
6. Summarize the changes, validation evidence, and remaining limitations.

## Project Contracts

- Follow the compatibility and quality expectations in [MISSION.md](docs/MISSION.md).
- Use the build and runtime checks in the [build verification plan](docs/plans/02-build-verification.md) when changing the Dockerfile, base images, or OIIO/OCIO versions.
- Keep planned capabilities separate from verified behavior; a documentation change does not establish that the image builds, that the OIIO tools run, or that the Python bindings import.

When a request conflicts with a documented contract, identify and resolve the conflict before changing that contract.
