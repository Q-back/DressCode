Each section is an ordered, commit-sized outcome. Finish its implementation, tests and documentation, run the relevant checks, inspect the diff and added-line count, and commit before starting the next group. Each group must leave the project working with all preceding groups; commands not yet implemented remain explicit exit-`2` placeholders and documented as unavailable. Review each committed group and keep review fixes in separate commits. This is design-only work, so there is no released CLI or stored state to migrate.

## 1. Commit: Establish the installable CLI skeleton

- [ ] 1.1 Init a `uv` project: `pyproject.toml` with `requires-python = ">=3.14,<3.15"`, package `dresscode`, entry point `dresscode = "dresscode.cli:main"`, runtime deps `typer` and `rich`, dev deps `pytest`, `ruff`, `ty`, `pre-commit`; `.python-version` pin.
- [ ] 1.2 Package skeleton `dresscode/{__init__,cli,config,entries,repo,diff,run,gate,report,context}.py`; `cli.py` exposes a `typer` app whose v0 commands exist and exit `2` as unimplemented. No attestation command or harness adapter module.
- [ ] 1.3 Test scaffolding: `testpaths = ["dresscode"]`, colocated `test_*.py`, a `git_repo` fixture building a real temporary repository with a base branch and a feature branch, and an `xdg_home` fixture pointing `XDG_STATE_HOME`/`XDG_CONFIG_HOME` at a temp dir so no test touches the real store.
- [ ] 1.4 Test: `dresscode --help` exits `0`, lists every v0 command and does not advertise `attest`; placeholders exit `2`.
- [ ] 1.5 Document installation, `--help` and the currently unavailable commands in the README; keep that status current in each following group.

## 2. Commit: Configure, author and list sealed questions

- [ ] 2.1 Implement `repo.py`: identity from the normalized `origin` URL, fallback to the main worktree realpath, identical from a linked worktree; exit `2` outside a git work tree.
- [ ] 2.2 Implement `config.py`: load and merge the three layers (private per-repo, repository-local file or directory, global), scalars overriding, missing layers tolerated, invalid TOML exiting `2` with the file named.
- [ ] 2.3 Implement `entries.py`: entry parsing with required `id`/`question`/`expects`, optional `reveal`/`context`/`enabled`, unknown keys rejected, merge by `id`, `enabled = false` dropping an entry.
- [ ] 2.4 Implement the counter store in the global store, independent of the configuration layers.
- [ ] 2.5 Implement `dresscode add --layer`, `dresscode retire <id> --reason` and basic `dresscode list` with `--json`, emitting enabled, non-retired entries as `id` and `question`, never `expects` or `reveal`. Context execution is unavailable until commit group 6.
- [ ] 2.6 Tests: two clone URL shapes resolving equal; worktree identity; each layer winning in turn using supported settings such as `base_ref`; missing required key and unknown key errors; merge and disable; counters writable with a read-only repository layer; `add` round-tripping into `list`; retired entries absent; no sealed keys in `list --json`.
- [ ] 2.7 Document the three configuration layers, entry fields, authoring commands and sealed listing; note that context commands are not executed yet.

## 3. Commit: Define and fingerprint the current diff

- [ ] 3.1 Implement base ref resolution with the configured → `origin/HEAD` → `main`/`master` → root commit chain, reporting the resolved base.
- [ ] 3.2 Implement the scoped diff: `git diff --merge-base <base>` against the working tree, plus untracked non-ignored files as additions.
- [ ] 3.3 Implement `diff.exclude` with the documented defaults, applied to listing and counting.
- [ ] 3.4 Implement the fingerprint over scoped content: stable when nothing changes, different after a scoped edit, unchanged by an excluded edit.
- [ ] 3.5 Implement `dresscode diff` with `--numstat` and `--json`.
- [ ] 3.6 Tests against the real temporary repository, no mocking of git: committed plus staged plus unstaged all counted; base-moved-on case; untracked included, ignored excluded; lockfile excluded by default; the three fingerprint properties; staging and committing unchanged scoped content preserving the fingerprint when the merge base is unchanged.
- [ ] 3.7 Document base resolution, working-tree and untracked scope, exclusions and `diff` output.

## 4. Commit: Record diff-bound verdicts without identity checks

- [ ] 4.1 Implement the run key (repo identity plus branch, `detached-<sha>` fallback) and JSON run state under `$XDG_STATE_HOME/dresscode/runs/`; assert in tests that the repository stays untouched. Do not detect or record implementer or reviewer session identities.
- [ ] 4.2 Implement `dresscode answer` with required evidence, fingerprint pinning, timestamps, counter updates, reveal in the response, re-answer replacing and history kept; `--n-a` never failing the gate. Accept otherwise valid answers without attestation or session identity.
- [ ] 4.3 Implement staleness against the current fingerprint, and `dresscode reset` clearing the run's verdicts and waivers while preserving counters.
- [ ] 4.4 Tests: branch switch isolating runs; detached HEAD; first answer accepted without attestation or identity; supplied session environment variables neither recorded nor used to reject answers; reveal returned only after recording; empty evidence and unknown id exiting `2`; re-answer history; `n-a` counters; scoped edit staling a verdict while an excluded edit does not; reset clearing verdicts and keeping counters.
- [ ] 4.5 Document `list` → `answer`, evidence, reveal, run state, staleness and reset. Require a fresh-context reviewer through `AGENTS.md` or the harness instructions, while stating that the CLI cannot enforce reviewer independence.

## 5. Commit: Gate current verdicts and documented waivers

- [ ] 5.1 Implement `dresscode check`: green condition, blocking states (`unanswered`, `stale`, `context_failed`, `violated`), the fixing command per entry, exit codes `0`/`1`/`2`, and `--json`. Reviewer freshness is not a gate condition.
- [ ] 5.2 Implement `dresscode waive`: only over a violating current verdict, reason required, reason/timestamp/fingerprint stored without author session identity, status `passed-with-waivers`, staleness like a verdict.
- [ ] 5.3 Implement `check --strict` applying the normal gate checks and additionally failing on waivers only, not on unverified reviewer freshness.
- [ ] 5.4 Implement `dresscode report` with `rich`: status, diff size, reviewer freshness explicitly `unverified`, per-entry verdict with evidence and reveal, waivers in their own section, no ANSI when not a TTY; `report --json` includes `reviewer_freshness: "unverified"`.
- [ ] 5.5 Tests: green run; empty entry list; each blocking state naming its command; usage error exiting `2` while a failing gate exits `1`; waiver flipping the gate and `--strict` flipping it back; waiver over a satisfied entry refused; stale waivers blocking; reset clearing waivers; both gate modes green without waivers despite unverified freshness; report content, JSON limitation and non-TTY plainness.
- [ ] 5.6 Document `check`, `waive`, `check --strict`, `report` and exit codes. The gate runs before final task hand-over, not before intermediate commits, and does not install or require Git hooks. A green gate means current recorded answers satisfy the entries, not proof of independent review; strict mode adds a no-waiver requirement only.

## 6. Commit: Supply trusted context evidence end to end

- [ ] 6.1 Implement context execution from the repository root when `list` builds an entry, attaching captured stdout to its question, with an output cap, a truncation marker and `context.timeout_seconds` (default `10`).
- [ ] 6.2 Implement the trust store: repository-local commands blocked until `dresscode trust`, trust bound to a content hash of the repository-local layer, private and global layers always trusted.
- [ ] 6.3 Implement `context_failed` on non-zero exit or timeout, with the stderr tail surfaced and `check` blocking.
- [ ] 6.4 Implement recording the context output into the run state when answering and showing it in `report`.
- [ ] 6.5 Tests: context output delivered in `list` without sealed fields; untrusted clone runs nothing and names `dresscode trust`; trust granted then invalidated by an edit; failing and hanging commands both landing as `context_failed`; recorded output appearing in the report; truncation marker.
- [ ] 6.6 Document an example entry using `dresscode diff --numstat`, trust, timeouts and failure output; remove the interim context-unavailable limitation.

## 7. Commit: Verify the full workflow and publish usage

- [ ] 7.1 End-to-end test over a real temporary repository with as few mocks as possible: `check` (red) → two intermediate commits succeeding without answers → `check` still red → `diff` showing both commits → `list` → `answer` for every entry including one violation → `waive` → `check` green with `passed-with-waivers` → `check --strict` red → `report` showing the waiver and reviewer freshness `unverified`; then edit a file and assert both verdicts and waivers go stale.
- [ ] 7.2 End-to-end test without harness/session environment variables or attestation: the same calling environment runs `check`, `list` and valid matching answers → both `check` and `check --strict` green without waivers → `report --json` showing reviewer freshness `unverified`.
- [ ] 7.3 `uv tool install .` from the repo, run `dresscode check` in a real project, confirm the store lands under `$XDG_STATE_HOME` and the repository is untouched.
- [ ] 7.4 Add `.pre-commit-config.yaml` for deterministic development checks (`ruff-format`, `ty`) only; do not add a `dresscode check` hook.
- [ ] 7.5 Complete the README install and usage sections (`uv tool install .`, `uv tool install --force --refresh .`, `uv run dresscode`), the three configuration layers, an example entry with a context command, the exit-code table and fresh-reviewer harness instructions requiring `dresscode check` before declaring the task done, with intermediate commits unrestricted by DressCode. Remove placeholder notices and make clear that reviewer independence is unverified and `--strict` rejects waivers only.
