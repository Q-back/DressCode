# DressCode

DressCode is a CLI that turns recurring AI coding-agent mistakes into yes/no
code-review questions. The expected answer stays sealed until the reviewer records
a verdict. When only reviewing code, record answers and report findings. When
changing code, use `dresscode check` to require passing answers or documented
exceptions before you're done.

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14. From this checkout:

```sh
uv tool install .
dresscode --help
```

Ensure uv's tool binary directory is on your `PATH` (`uv tool update-shell` can set it up). After updating this checkout, rebuild and replace the installed tool:

```sh
uv tool install --force --refresh .
```

Without a tool installation, run from the checkout:

```sh
uv run dresscode --help
```

## Agent skill

`dresscode --skill` prints a short, standalone `SKILL.md` to stdout and exits
successfully, even outside a Git repository. It covers setup, the review workflow,
and authoring useful rules. It reads no project configuration and changes nothing.
The skill's review flow records verdicts and reports findings; it does not edit
reviewed code or grant waivers. The calling workflow handles fixes and accepted
exceptions.

Give the output to an agent directly, or save it as `SKILL.md` in a skill directory
supported by your agent harness. Installation and activation are up to you:

```sh
dresscode --skill > SKILL.md
```

## Usage

Run the installed `dresscode` command from the target Git repository. Configure
questions using `dresscode add` or the TOML layers below; no questions are seeded.

```text
list → fresh-context reviewer → answer → report
```

- **Changing code?** Run tests first. The review reports findings; the calling
  workflow handles fixes and explicitly accepted exceptions. Obtain new verdicts
  after edits and require `dresscode check` to pass before you're done.
- **Only reviewing code?** Answer every question with evidence and report the
  problems. Do not change reviewed code, add waivers or run `dresscode check`.
  Surface unanswered questions, stale answers, context failures and command
  errors rather than treating them as completed checks.

Every command supports `--help` (exit `0`) and `--json`. JSON output is a single document on stdout; configuration, state and environment errors use `{"status": "error", "error": "..."}` and exit `2`.

## Repository identity

Run commands inside a Git work tree. Outside one, commands exit `2` with a clear error (or a JSON error with `--json`); help and `dresscode --skill` remain available anywhere.

Repositories are identified by their `origin` URL from the shared clone configuration (worktree-specific overrides do not change identity), after removing the scheme, credentials, trailing slash and `.git` suffix. For example, `git@example.com:team/repo.git` and `https://example.com/team/repo` both identify `example.com/team/repo`. With no origin, the identity is the real path of the main worktree. Linked worktrees share that identity, even without a remote. Discovering identity does not write configuration or state.

## Configuration

Configuration is optional and read from lowest to highest priority:

| Priority | Location |
|---|---|
| Global defaults | `$XDG_CONFIG_HOME/dresscode/config.toml` |
| Repository | `.dresscode/*.toml` in filename order, or `.dresscode.toml` if `.dresscode/` is absent |
| Private per-repository overrides | `$XDG_CONFIG_HOME/dresscode/repos/<encoded-repo-id>.toml` |

`XDG_CONFIG_HOME` defaults to `~/.config`. The private filename is the repository identity percent-encoded as one filename: `example.com/team/repo` becomes `example.com%2Fteam%2Frepo.toml`. Local-path fallback identities are encoded too, so private files cannot escape the configuration directory.

Higher layers replace scalar settings and lists; settings tables merge recursively. For example, private `merge_base_with = "origin/develop"` replaces repository `merge_base_with = "origin/main"`. Missing layers are ignored. Invalid TOML and invalid entries exit `2` with the source file named, including with `--json`.

Entries use TOML arrays of tables:

```toml
merge_base_with = "origin/main"

[[entries]]
id = "test-factory"
question = "Did you reuse an existing test factory?"
expects = true
reveal = "Prefer the existing factory over a hand-rolled mock."
```

`id` and `question` must be strings and `expects` must be boolean. Optional fields are `reveal` (string, default empty), `context` (shell-command string) and `enabled` (boolean, default true). Unknown entry keys are rejected. Entries merge by `id`: a higher layer can supply only the fields it overrides, preserving the rest. Setting `enabled = false` removes an entry from the effective list.

Context commands execute during `list`, subject to the trust policy below. Loading configuration alone does not execute commands.

## Author and list questions

From the target repository:

```sh
dresscode add test-factory \
  --question "Did you reuse an existing test factory?" \
  --expects true \
  --reveal "Prefer the existing factory over a hand-rolled mock."
dresscode list
dresscode list --json
# {"entries": [{"id": "test-factory", "question": "Did you reuse an existing test factory?"}]}
dresscode retire test-factory --reason "now an ast-grep rule"
```

`add <id>` requires `--question` and `--expects true|false`. Optional flags are `--reveal`, `--context`, `--layer repo|private|global` (default `repo`) and `--json`. It appends a definition without dropping comments or unrelated TOML settings. With `.dresscode/`, it uses the last existing TOML file in filename order, or `rules.toml` if the directory is empty. Otherwise it writes `.dresscode.toml`. Global and private destinations are the files in the configuration table above. Layer precedence still applies to repeated IDs.

`list` emits only enabled, non-retired entries as `id` and `question`, plus context evidence when configured, in both text and JSON. It never exposes `expects` or `reveal` and does not increment counters. An empty list is successful; `--json` returns `{"entries": []}`. Reading an empty store creates no state files.

`retire <id> [--reason <text>]` removes an entry from future listings for this repository, across branches and linked worktrees. The reason is optional and defaults to empty. Retirement preserves the entry snapshot, reason and timestamp in `$XDG_STATE_HOME/dresscode/entries.sqlite3` (default state home: `~/.local/state`). Existing counters are kept, and configuration files are not modified. Unknown or already-retired IDs exit `2`.

The same SQLite store holds per-repository, per-entry counters: `asked`, `violated`, `n_a` and `last_violated`. Counter writes are independent of configuration permissions. Retirement history is readable in the `retired` table; its `entry` column contains the original entry as JSON. Each recorded answer increments `asked`; violations and `n-a` answers update their respective counters.

## Trusted context evidence

An entry can supply a read-only shell command as evidence:

```toml
[context]
timeout_seconds = 10

[[entries]]
id = "change-size"
question = "Are the added lines under 400?"
expects = true
reveal = "Keep changes small enough to review in one sitting."
context = "dresscode diff --numstat"
```

Inspect repository-local commands before allowing them to run:

```sh
dresscode trust
dresscode list
dresscode answer change-size --yes --evidence "Reviewed the listed totals."
dresscode report
```

`trust` approves the current repository-local TOML filenames and contents for
this checkout. Adding, removing, renaming or editing a layer file requires trust
again. Approval is stored under `$XDG_STATE_HOME/dresscode/trust/`, never in the
repository. Separate clones and linked worktrees need their own approval.
Commands inherited from private or global configuration are always trusted;
overriding only a question does not change the command's source layer.

`list` runs trusted commands through the shell from the repository root, even
when invoked in a subdirectory. Commands run with your permissions; DressCode
cannot enforce read-only behavior. Trust approves configuration, not the contents
of scripts it invokes. Use commands you understand and keep their dependencies
under review.

Context entries add `state`, `context_output` (trimmed stdout) and `error` to
`list --json`. Untrusted local commands run nothing and report
`context_untrusted`, naming `dresscode trust`. Non-zero exits and timeouts report
`context_failed`, including the exit code or timeout and the last 4 KiB of stderr.
The timeout defaults to 10 seconds; `context.timeout_seconds` must be a positive,
finite number. Timeout terminates the shell and its process group. Stdout keeps
its first 16 KiB, with `[truncated]` appended when more was emitted; capture uses
bounded memory. Listing succeeds while surfacing these per-entry blockers;
`check` exits `1` for them, even with an earlier passing or `n-a` answer.

`list` saves delivered context in global run state, tied to the current diff and
command. For context entries, `answer` requires a successful current delivery;
run `list` again after changing the diff or command. A changed or removed command
also stales existing answers and waivers; relisting alone cannot renew them.
`answer` copies the delivered output and command into the verdict, rather than
rerunning the command. `report` shows the recorded
`context_output` beside the verdict in text and JSON. Neither `check` nor `report`
executes commands. Reset also clears delivered context.

## Record and reset a review

Give the listed question to a fresh-context reviewer, then record its answer with
non-empty evidence:

```sh
dresscode list
dresscode answer test-factory --yes --evidence "Reused the shared fixture."
dresscode answer python-only-rule --n-a --evidence "This change touches no Python."
```

Choose exactly one of `--yes`, `--no` or `--n-a`. The response gives the expected
answer and reveal only after the verdict and evidence have been saved. An `n-a`
answer still needs evidence and is treated as satisfied by the gate. Answering an
ID again replaces its current verdict and preserves the previous answer in run
history.

Run state is JSON in `$XDG_STATE_HOME/dresscode/runs/` (default:
`~/.local/state/dresscode/runs/`). Each repository, branch and resolved baseline commit has a separate run;
detached checkouts use `detached-<short-sha>`. Every answer records the current
diff fingerprint and timestamp. A scoped change makes the verdict stale and
requires a new answer before `dresscode check` can pass. Excluded changes do
not stale it. `dresscode reset` clears current verdicts and waivers for this run
without changing counters; past re-answers remain in history.

Every successful review command includes top-level `run_key` and `base_commit`
in JSON and identifies the baseline in text. The run key uses a versioned
namespace; a changed default baseline starts a separate review even when its
content fingerprint matches. Equivalent default targets share a run when their
merge bases match. Context subprocesses receive the pinned baseline through
`DRESSCODE_BASE_COMMIT`; nested review commands use it before default selection.

Legacy runs lack baseline identity. Their files stay untouched, but cannot
supply answers, context or waivers to new runs. Review again after upgrading;
counters, retirements and context trust are retained. **After downgrading, run
the legacy `dresscode reset` in every repository/branch before relying on its
gate, then review again.** Older binaries can otherwise reuse retained approvals.

The project `AGENTS.md` requires a fresh-context reviewer that did not see the
implementation transcript. DressCode records the verdict but does not verify
reviewer independence.

## Gate hand-over and report the result

```sh
dresscode check
dresscode waive test-factory --reason "Existing setup cannot use the shared fixture."
dresscode check --json
dresscode check --strict
dresscode report
```

`check` requires every enabled, non-retired entry to have a current matching or
`n-a` verdict, or a current waiver. No entries means a pass. Its status is
`passed`, `passed-with-waivers`, or `failed`. For each blocker, it names the ID,
question, state (`unanswered`, `stale`, `context_untrusted`, `context_failed`, or `violated`) and the
next commands. `check --json` returns `status` and `entries`, each with `id`,
`question`, `state` and `commands`, plus `error` for context blockers, without
revealing sealed fields.

`waive <id> --reason <text>` requires a non-empty reason and a **current violating
verdict**. It cannot replace an unanswered, stale, matching or `n-a` answer.
The reason, timestamp and diff fingerprint are stored in the run. A scoped edit
expires the waiver; re-answering removes it, and reset clears all current waivers.
`check --strict` performs the same checks and additionally fails on waivers,
listing them instead of accepting a documented violation.

`report` shows overall status and added/removed lines, followed by separate rule
blocks. Each block starts with a separator and a `Rule: <id> [state]` heading.
Bold, colored headings and verdicts lead to a prominent Evidence label and
indented evidence. Question and Reveal stay visible with muted styling.
Matching answers and `n-a` keep a compact verdict; conflicting yes/no answers
add the expectation inline, such as `Verdict: no (expected yes)`.
A matching yes/no verdict stays green when stale; its `[stale]` state stays yellow.
Unanswered rules show `Verdict: unanswered` without sealed fields. Recorded
context and context errors stay in their rule's block. Waivers and their reasons
have a separate section, with stale waivers labeled. Separators, labels and
spacing preserve the grouping in redirected output, which has no ANSI colors.
`report --json` includes `status`, `run_key`, `diff`, `entries` and `waivers`.
Reporting a blocked run succeeds; a report with status `failed` can contain
review findings, unanswered questions or other blockers. A successful report
command does not prove the review is complete or the code passes. Use `check`
when the code must pass before you're done.

| Exit | Meaning |
|---|---|
| `0` | Success; for `check`, all entries pass or have accepted waivers |
| `1` | `check` needs action; strict mode also rejects waivers |
| `2` | Usage, configuration, state or environment error |

When changing code, require a fresh-context reviewer and a successful
`dresscode check` **before calling the changes done**, through `AGENTS.md` or the
harness. Intermediate commits remain unrestricted, and DressCode does not install
or require Git hooks.
A green gate means the recorded answers satisfy the current entries; it does not
prove reviewer independence. Strict mode adds a no-waiver requirement.

### Harness instructions

Add this to a target project's `AGENTS.md` or equivalent harness instructions:

```text
Before declaring code changes done, request a fresh-context reviewer who has
not seen the implementation transcript. Give it the final cumulative diff
(including uncommitted work) and the questions from dresscode list --json,
not the sealed expectations or reveals. Record every answer with evidence
using dresscode answer; use n-a with evidence when a question does not apply.
The main task, not the review skill, resolves violations or records explicitly
accepted waivers with reasons.
Require dresscode check to exit 0 before hand-over, and show dresscode report.
If the reviewed diff changes, obtain current answers before checking again.
Intermediate commits do not need current DressCode verdicts.
A passing check records answers; it does not prove reviewer independence.

When only reviewing code, record every answer with evidence and report problems.
Do not change reviewed code, add waivers or run dresscode check. Surface
unanswered questions, stale answers, context failures and command errors instead
of treating them as completed checks.
```

Use `dresscode check --strict` instead when the project must reject waivers.
DressCode does not launch the reviewer; the agent or harness owns that step.

## Inspect the current diff

```sh
dresscode diff
dresscode diff --numstat
dresscode diff --json
```

By default, the scope is the merge base of `HEAD` and the resolved target compared with the **working tree**, plus untracked, non-ignored files as additions. It includes committed, staged and unstaged changes together, not just the index or last commit. Commits added to the base branch after your branch split are not part of the review. Commands work from any subdirectory and report paths relative to the repository root. Inspecting a diff does not write repository files or state.

Base resolution uses the first available candidate:

```text
configured merge_base_with → origin/HEAD → local main → local master → root commit
```

A configured `merge_base_with` must resolve to a commit; an invalid value exits `2` rather than silently choosing another base. A repository with no commits also exits `2`. The output identifies the resolved merge-base commit as `base_commit`.

### Review an exact commit

`diff REF` is shorthand for `diff --base REF`. All seven review commands accept
`--base REF`: `diff`, `list`, `answer`, `waive`, `check`, `report` and `reset`.
An explicit ref selects its exact commit, including diverged or unrelated
history; it does not calculate a merge base or resolve the unused default target.
Branches, remote-tracking refs, lightweight/annotated tags, commit IDs and
single-commit expressions such as `HEAD~2` work. Git refname precedence applies;
use `refs/heads/name` or `refs/tags/name` to disambiguate collisions. Empty or
invalid refs, ambiguous abbreviated IDs, ranges and blob/tree IDs exit `2`.
Supplying both positional REF and `--base` also exits `2`. Revision errors under
`--json` emit one error document on stdout and leave stderr empty.

Pin a SHA across commands so a moving branch or tag cannot change the review:

```sh
dresscode diff HEAD~2 --numstat
BASE=$(git rev-parse HEAD~2)
dresscode list --base "$BASE" --json
dresscode answer test-factory --base "$BASE" --yes --evidence "Reused the shared fixture."
dresscode check --base "$BASE" --strict
dresscode report --base "$BASE"
dresscode reset --base "$BASE"
```

To accept a current violation, record the reviewer's violating verdict first,
then use `dresscode waive test-factory --base "$BASE" --reason "<reason>"`.
The ordinary gate accepts that waiver; `check --strict --base "$BASE"` rejects it.
Gate repair commands pin the resolved SHA too.

Selection priority is explicit REF, inherited `DRESSCODE_BASE_COMMIT`, then the
default merge base. Context subprocesses inherit the parent's already resolved
SHA; an explicit child ref can supply auxiliary evidence without changing the
parent scope. Inspection never changes the selector for later invocations.
Equivalent selectors share a run only when their baseline SHAs match. Different
baselines keep separate answers, history, context and waivers even if content
fingerprints match. Reset clears only the selected run; counters remain shared.

### Exclusions

`diff.exclude` is a list of Git pathspecs, applied to both tracked and untracked files, listing and counts. An explicit list **replaces** the defaults; `exclude = []` includes everything in scope. For example:

```toml
[diff]
exclude = ["*.lock", ":(glob)**/generated/**"]
```

The default pathspecs are:

| Category | Pathspecs |
|---|---|
| Lockfiles | `:(glob)**/*.lock`, `:(glob)**/*-lock.json`, `:(glob)**/npm-shrinkwrap.json`, `:(glob)**/go.sum`, `:(glob)**/packages.lock.json` |
| Vendored code | `:(glob)**/vendor/**` |
| Snapshots | `:(glob)**/snapshots/**`, `:(glob)**/__snapshots__/**` |
| Cassettes and fixtures | `:(glob)**/cassettes/**`, `:(glob)**/fixtures/**` |

### Output and fingerprints

Text output lists added lines, removed lines and each path, followed by totals. `--numstat` omits the column header and sends the base description to stderr, leaving tab-separated rows on stdout with totals last:

```text
2       0       src/new.py
2       0       TOTAL
```

Binary files use `-` for both counts and do not contribute to line totals. Paths containing tabs, newlines, quotes or backslashes are JSON-quoted so each file stays on one output line. Renames are shown as a deletion plus an addition, so moving unchanged content into scope still counts its added lines. Counts never subtract deletions from additions, and DressCode has no built-in size threshold.

`--json` emits one document with `run_key`, `base_commit`, `fingerprint`, `files` (`path`, `added`, `removed`) and `totals` (`added`, `removed`). Binary file counts are `null`. JSON takes precedence if combined with `--numstat`; successful output has no stderr text. An empty diff succeeds with an empty file list and zero totals.

The SHA-256 fingerprint covers scoped paths, baseline blobs, file modes and current content (symlinks use the link text, not the target). It stays stable across repeated reads and excluded edits. Staging or committing unchanged scoped content also preserves it when the merge base is unchanged. Removing a path from the index alone does not change the result, including when `core.filemode=false` ignores filesystem executable-bit changes. If re-adding the file records a different Git executable mode, that is a scoped change and the fingerprint changes. A scoped content edit changes it even if the line counts stay the same. This is the value used to bind review answers to the reviewed changes.

An untracked nested Git repository exits `2` with a named error rather than being silently skipped. Add it as a submodule or explicitly exclude its path with `diff.exclude`.

### Submodules

Clean submodules are reviewed as Gitlink commit-ID changes only. Their internal file diffs are not expanded into the listing, line counts or fingerprint. Staging or committing an unchanged parent pointer preserves its fingerprint, regardless of Git’s submodule display setting.

A non-excluded, initialized submodule with staged edits, unstaged edits or non-ignored untracked files makes `diff` exit `2` without producing a diff or fingerprint. Dirty nested submodules also block it; Git settings that hide submodule changes do not bypass this check. The error names the submodule and explains the remedies: commit changes inside it and update the parent pointer, or explicitly exclude the submodule path with `diff.exclude`. Ignored files alone do not block inspection.

With `--json`, this is a single `{"status": "error", "error": "..."}` document, not a successful result. DressCode does not modify files, reset submodules, automatically exclude them or block Git commits.

## Development

The development interpreter is pinned in `.python-version`. `uv` manages the environment and dependencies:

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

For an editable tool installation, use `uv tool install --editable .` and keep
this checkout in place. Source edits take effect on the next invocation;
reinstall with `uv tool install --force --editable .` after changing dependencies
or entry points.

Tests live alongside the package modules. Each test gets temporary XDG config and state directories; Git tests use a real temporary repository, not the checkout. End-to-end tests invoke the CLI in separate processes and exercise reviews with and without waivers.

The optional development hooks run Ruff formatting, Ruff linting and `ty` only:

```sh
uv run pre-commit install
uv run pre-commit run --all-files
```

These deterministic checks do not run `dresscode check` or require review answers
for intermediate commits. Installing these development hooks is optional and
separate from using DressCode as a hand-over gate.

GitHub Actions runs these checks on Ubuntu for every push and pull request, using the Python version in `.python-version` and locked dependencies from `uv.lock`. You can also start the `CI` workflow manually from the Actions tab. To block merges when checks fail, require `Python checks` in the branch protection rule or ruleset for your default branch.

## Boundaries

DressCode is a pure CLI over a state store plus git. It never spawns agents, never calls a model, never edits code.

For code changes, `AGENTS.md` or the harness instructions require a fresh-context
review and a passing `dresscode check` before the agent declares the changes done.
When only reviewing code, report findings without changing reviewed code, adding
waivers or running `dresscode check`. Intermediate commits do not need to pass
DressCode: the gate covers the final cumulative diff, including uncommitted work,
not individual commits.
DressCode does not install or require Git hooks. V0 gates recorded answers against
the current diff; passing is not proof of independent review.
`dresscode check --strict` additionally rejects waivers.

State is global, never in the repo: run state under `$XDG_STATE_HOME/dresscode/`, keyed by repo and branch. Config is layered — private per-repo, then the repo's own `.dresscode/`, then your global defaults.
