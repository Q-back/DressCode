# Design

## Context

`dresscode/cli.py` currently prints the bundled `SKILL.md` unchanged. Existing tests require export to work without Git, configuration access or writes. See `proposal.md` for motivation and `specs/skill-export/spec.md` for the contract.

## Goals / Non-Goals

Keep this to a small renderer using the standard library. Do not infer checkout revisions, add build-time revision stamping, or change installation tooling.

## Decisions

- Read the installed `dresscode` distribution's `direct_url.json` with `importlib.metadata`. Use `vcs_info.commit_id`, not the requested branch or tag. This avoids Git subprocesses and packaging hooks.
- Accept only Git metadata for `https://github.com/Q-back/DressCode` with optional `.git`, a full hexadecimal Git commit ID, and no editable indication. Do not copy arbitrary metadata URLs into shell commands.
- On absent, unreadable or invalid metadata, return the bundled Markdown unchanged. This deliberately leaves local, editable, wheel-only and unsupported-origin installs on the existing checkout instructions.
- Replace only the checkout-install sentence in memory when a pin is available. Keep the bundled Markdown usable by itself; add no new first fenced `sh` block, since the existing example test executes it as a DressCode command.

## Risks / Trade-offs

- uv's Git-install metadata has not been verified in this checkout. Require an offline real-uv Git installation test before accepting the implementation; use a temporary repository, not the network or the user's tool installation. Test exported pin rendering with realistic upstream metadata separately.
- A source commit does not lock dependencies. Describe the command as a source pin, not a fully reproducible environment.
- Unsupported URL forms intentionally fall back instead of adding URL normalization machinery.
