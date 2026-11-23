# Design

## Context

`dresscode/cli.py` currently prints the bundled `SKILL.md` unchanged. Existing tests require export to work without Git, configuration access or writes. See `proposal.md` for motivation and `specs/skill-export/spec.md` for the contract.

## Goals / Non-Goals

Keep this to a small renderer using the standard library. Do not infer checkout revisions, add build-time revision stamping, or change installation tooling.

## Decisions

- Read `direct_url.json`, the installed package's record of where it came from, using `importlib.metadata`. Take the repository URL from `url` and the exact Git commit from `vcs_info.commit_id`. Do not use the requested branch or tag, which may move. This avoids Git subprocesses and packaging hooks.
- Use the metadata URL so forks work too. Require Git metadata and a full hexadecimal Git commit ID. Parse the URL with `urllib.parse.urlsplit`, validate it against the supported-URL contract in `specs/skill-export/spec.md`, then use `shlex.quote` on the complete `git+<url>@<commit>` argument. Do not restrict the repository to the official upstream.
- Accept HTTPS and `ssh://` metadata URLs under the same host, path, port and shell-safety checks. Allow SSH usernames because Git servers commonly require `git@host`; reject SSH passwords and keep HTTPS user information unsupported. Preserve the source URL, including an SSH username and explicit port, rather than translating it to HTTPS. Do not normalize SCP-style sources. Authentication remains the installer's responsibility through their SSH configuration and keys.
- Put the official unpinned install command in the bundled setup sentence: `uv tool install 'git+https://github.com/Q-back/DressCode.git'`. On absent, unreadable, invalid or unsupported metadata, return that bundled Markdown unchanged. Treat any `subdirectory` field as unsupported so the command cannot target the repository root instead of the installed package.
- When a pin is available, replace only the bundled install sentence in memory. Keep the Markdown usable by itself, with no placeholders.
- Both setup forms tell agents how to install DressCode if it is missing. Do not special-case editable installs or mention them in skill instructions; usable source metadata alone controls whether a pin is generated.

## Validation

Offline `uv tool install` checks with uv 0.10.8 confirmed `direct_url.json` for unpinned, branch, tag and full-commit installs from a temporary `git+file://` repository. Reading it through `importlib.metadata` returned the repository URL, `vcs_info.vcs` set to `git` and the full resolved `vcs_info.commit_id`. Branch and tag names appeared separately in `vcs_info.requested_revision`.

The checks used isolated temporary tool, executable and cache directories, without network access or changes to the user's tools. Preserve these cases as an automated regression test before accepting the implementation.

The file URL verifies uv's Git metadata format, not a supported export source. CLI tests must separately cover pin rendering with realistic official-repository and fork HTTPS and SSH metadata. SSH cases must cover URLs with and without usernames, explicit ports, password rejection, malformed authorities and shell quoting. These tests must not need network access, SSH keys or a live Git server.

## Risks / Trade-offs

- A source commit does not lock dependencies. Describe the command as a source pin, not a fully reproducible environment.
- The fallback follows the official repository's default branch and may not match the exported instructions exactly. Document it as an unpinned fallback, not a matching-source guarantee.
- Unsupported URL forms intentionally fall back instead of adding URL normalization machinery.
