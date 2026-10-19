# DressCode

DressCode is a CLI that remembers the mistakes an AI coding agent actually makes and hands them back as questions before task hand-over. Questions are boolean, the wanted answer is sealed until the reviewer has committed to one, and `dresscode check` stays red until every question is answered as expected or the violation is documented with a reason.

**Status:** help, repository discovery and configuration validation work. All review and entry commands remain unavailable and exit `2`. Configuration is read but not written; no review state is read or written. The intended behavior is specified in `openspec/changes/add-dresscode-cli/`.

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14. From this checkout:

```sh
uv tool install .
dresscode --help
```

Ensure uv's tool binary directory is on your `PATH` (`uv tool update-shell` can set it up). To reinstall after updating the checkout:

```sh
uv tool install --force --refresh .
```

Without a tool installation, run from the checkout:

```sh
uv run dresscode --help
```

## Command availability

The following commands are placeholders, not a working review workflow:

```text
add  answer  check  diff  list  report  reset  retire  trust  waive
```

Each supports `--help` (exit `0`) and `--json`; command-specific arguments and review behavior are not implemented. A bare command validates the repository and configuration, then prints an unavailable message to stderr and exits `2`. With `--json`, it emits a single JSON document on stdout instead, still exiting `2`:

```sh
uv run dresscode check --json
# {"command": "check", "status": "unimplemented"}
```

Do not use `dresscode check` as a hand-over gate until it is implemented.

## Repository identity

Run commands inside a Git work tree. Outside one, commands exit `2` with a clear error (or a JSON error with `--json`); help remains available anywhere.

Repositories are identified by their `origin` URL from the shared clone configuration (worktree-specific overrides do not change identity), after removing the scheme, credentials, trailing slash and `.git` suffix. For example, `git@example.com:team/repo.git` and `https://example.com/team/repo` both identify `example.com/team/repo`. With no origin, the identity is the real path of the main worktree. Linked worktrees share that identity, even without a remote. Discovering identity does not write configuration or state.

## Configuration

Configuration is optional and read from lowest to highest priority:

| Priority | Location |
|---|---|
| Global defaults | `$XDG_CONFIG_HOME/dresscode/config.toml` |
| Repository | `.dresscode/*.toml` in filename order, or `.dresscode.toml` if `.dresscode/` is absent |
| Private per-repository overrides | `$XDG_CONFIG_HOME/dresscode/repos/<encoded-repo-id>.toml` |

`XDG_CONFIG_HOME` defaults to `~/.config`. The private filename is the repository identity percent-encoded as one filename: `example.com/team/repo` becomes `example.com%2Fteam%2Frepo.toml`. Local-path fallback identities are encoded too, so private files cannot escape the configuration directory.

Higher layers replace scalar settings and lists; settings tables merge recursively. For example, private `base_ref = "origin/develop"` replaces repository `base_ref = "origin/main"`. Missing layers are ignored. Invalid TOML and invalid entries exit `2` with the source file named, including with `--json`.

Entries use TOML arrays of tables:

```toml
base_ref = "origin/main"

[[entries]]
id = "test-factory"
question = "Did you reuse an existing test factory?"
expects = true
reveal = "Prefer the existing factory over a hand-rolled mock."
```

`id` and `question` must be strings and `expects` must be boolean. Optional fields are `reveal` (string, default empty), `context` (shell-command string) and `enabled` (boolean, default true). Unknown entry keys are rejected. Entries merge by `id`: a higher layer can supply only the fields it overrides, preserving the rest. Setting `enabled = false` removes an entry from the effective list.

**Context commands are stored as text only and are not executed.** Authoring and sealed listing are still unavailable; do not use the placeholder commands as a review workflow.

## Development

The development interpreter is pinned in `.python-version`. `uv` manages the environment and dependencies:

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

Tests live alongside the package modules. Each test gets temporary XDG config and state directories; Git tests use a real temporary repository, not the checkout.

## Planned behavior and boundaries

DressCode is a pure CLI over a state store plus git. It never spawns agents, never calls a model, never edits code.

`AGENTS.md` or the harness instructions require a fresh-context review and a passing `dresscode check` before the agent declares the task done. Intermediate commits do not need to pass DressCode: the gate covers the final cumulative diff, including uncommitted work, not individual commits. DressCode does not install or require Git hooks. V0 gates recorded answers against the current diff; passing is not proof of independent review. `dresscode check --strict` additionally rejects waivers.

State is global, never in the repo: run state under `$XDG_STATE_HOME/dresscode/`, keyed by repo and branch. Config is layered — private per-repo, then the repo's own `.dresscode/`, then your global defaults.
