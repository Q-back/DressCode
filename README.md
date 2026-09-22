# DressCode

DressCode is a CLI that remembers the mistakes an AI coding agent actually makes and hands them back as questions after every implementation. Questions are boolean, the wanted answer is sealed until the reviewer has committed to one, and `dresscode check` stays red until every question is answered as expected or the violation is documented with a reason.

Status: design only, nothing implemented yet; the shape lives in `openspec/changes/add-dresscode-cli/`. Planned as a Python CLI installed with `uv tool install .`.

## Boundaries

DressCode is a pure CLI over a state store plus git. It never spawns agents, never calls a model, never edits code.

Running the review after an implementation is asked for in `AGENTS.md`, the same way `mypy` and `pytest` already are, and backstopped by `dresscode check` in `pre-commit`.

State is global, never in the repo: run state under `$XDG_STATE_HOME/dresscode/`, keyed by repo and branch. Config is layered — private per-repo, then the repo's own `.dresscode/`, then your global defaults.
