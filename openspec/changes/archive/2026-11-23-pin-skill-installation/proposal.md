# Proposal

## Why

Generated skills should tell agents how to install DressCode if it is missing. Prefer the source version that produced the skill, including forks, without maintaining a SHA by hand.

## What Changes

- Add a revision-pinned install command to `dresscode --skill` using the repository URL and exact Git commit recorded in installed-package metadata.
- Use `uv tool install 'git+https://github.com/Q-back/DressCode.git'` in the bundled skill and as the export fallback when usable source metadata is unavailable. This installs from the official repository's default branch, not a pinned version.
- Preserve standalone, read-only skill output. Do not add Git discovery, packaging hooks, dependencies or configuration.

## Capabilities

### New Capabilities

- `skill-export`: Standalone Markdown export with installation instructions matched to the installed tool when possible.

### Modified Capabilities

None.

## Impact

A small skill-rendering change in `dresscode/cli.py` or one focused module, the bundled `dresscode/SKILL.md`, `dresscode/test_skill.py`, and brief setup documentation in `README.md` and `docs/manual.md`. No changes to review commands or generated consumer copies.
