---
id: containers
family: stack
applies: projects that build, run or clean up containers for local development
condition: before container work that a local-development task already needs
detect: ["Dockerfile", "Containerfile", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml", ".devcontainer/devcontainer.json"]
version: 1
---
**Context** — local development is iterative work on a changing tree in a dev image, a devcontainer
or a dev Compose stack; keep any production-parity choice the project made there. A CI
reproduction, a release image or a deploy build keeps its prescribed build and run, even on this
machine, under the project's and its organisation's rules. The project's instructions, then the
person's, win over this fragment.
**Bounds** — reuse a compatible dev image and mount the source where the engine can reach it
(a remote daemon resolves mounts on its own host; there, use the project's transfer or build
route); rebuild it when the platform, base,
toolchain or dependency inputs change, never once per worktree, branch or run. Reusable build state
and downloads go in named volumes, package caches in build cache mounts, incompatible build state
apart. Each worktree that runs at once gets its own Compose project name; check fixed ports and
volume names. Label what you create with the project and worktree. Use the active engine's own
commands (Podman has its own). Before a removal, know the daemon and builder you talk to, and inspect each target just before it, since others remove things
too: who made it, who else uses it, whether its state is disposable (a database in an
anonymous volume is not). A request to free space
grants removing this project's own disposable objects (its stopped containers and unused images)
once that check passes; a named volume, the build cache and another project's or owner's object
need the person's yes; never `docker system prune` or an `-a` prune. For space, name the engine (`docker context`, or the engine's own), measure
its backing disk (a `--rm` container's `df`, `docker system df`) and the host's, and say which is full: an
engine VM grows only into the host's free space. Estimate a gain from what only that object uses,
never from summed "reclaimable" figures; report only a measured gain.
**Mechanisms** — `runtime-check`: the mounts show the current source and dependencies.
**Completion bar** — after success or failure, the disposable objects the task started are gone,
dependency services included; each kept image, volume or cache is named with its size, what reuses
it and when to remove it; freed space is measured before and after.
**Distinguish** — created by this task ≠ disposable; dev environment ≠ CI reproduction ≠ release
image.
