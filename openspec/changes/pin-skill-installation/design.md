# Design

## Context

`dresscode/cli.py` currently prints the bundled `SKILL.md` unchanged. Existing tests require export to work without Git, configuration access or writes. See `proposal.md` for motivation and `specs/skill-export/spec.md` for the contract.

## Goals / Non-Goals

Keep this to a small renderer using the standard library. Do not infer checkout revisions, add build-time revision stamping, or change installation tooling.

## Decisions

- Read `direct_url.json`, the installed package's record of where it came from, using `importlib.metadata`. Take the repository URL from `url` and the exact Git commit from `vcs_info.commit_id`. Do not use the requested branch or tag, which may move. This avoids Git subprocesses and packaging hooks.
- Use the metadata URL so forks work too. Require Git metadata and a full hexadecimal Git commit ID. Parse the URL with `urllib.parse.urlsplit`, validate it against the supported-URL contract in `specs/skill-export/spec.md`, then use `shlex.quote` on the complete `git+<url>@<commit>` argument. Do not restrict the repository to the official upstream.
- Put the official unpinned install command in the bundled setup sentence: `uv tool install 'git+https://github.com/Q-back/DressCode.git'`. On absent, unreadable, invalid or unsupported metadata, return that bundled Markdown unchanged.
- When a pin is available, replace only the bundled install sentence in memory. Keep the Markdown usable by itself, with no placeholders.
- Both setup forms tell agents how to install DressCode if it is missing. Do not special-case editable installs or mention them in skill instructions; usable source metadata alone controls whether a pin is generated.

## Risks / Trade-offs

- uv's Git-install metadata has not been verified in this checkout. Require an offline real-uv Git installation test before accepting the implementation; use a temporary repository, not the network or the user's tool installation. Test exported pin rendering with realistic official-repository and fork metadata separately.
- A source commit does not lock dependencies. Describe the command as a source pin, not a fully reproducible environment.
- The fallback follows the official repository's default branch and may not match the exported instructions exactly. Document it as an unpinned fallback, not a matching-source guarantee.
- Unsupported URL forms intentionally fall back instead of adding URL normalization machinery.
