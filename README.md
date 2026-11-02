# oiio-docker
Installation of OIIO and OCIO for use in a VFX pipeline.

## Building with docker
The CY2021 build image is published for `linux/amd64` only, so name the platform explicitly. On an arm64 host such as Apple silicon, this runs under emulation:

```docker build --platform linux/amd64 -t algernon_vfx/oiio .```

## Running image in an interactive bash shell
```docker run -it --platform linux/amd64 --entrypoint='bash' algernon_vfx/oiio```

## Project documentation

- [Mission](docs/MISSION.md): purpose, architecture, and quality expectations.
- [Roadmap](docs/ROADMAP.md): phase status and the next planned work.
- [Git workflow](docs/GIT.md): branches, worktree safety, and signed commits.
- [Implementation log](docs/IMPLEMENTATION.md): decisions and validation history.
