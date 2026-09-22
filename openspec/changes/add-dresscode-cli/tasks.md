Sections 1–3 are one sitting, then one sitting each for 4, 5 and 6+7. Every section ends green: tests pass and the commands it names work end to end.

## 1. Project scaffolding

- [ ] 1.1 Init a `uv` project: `pyproject.toml` with `requires-python = ">=3.14,<3.15"`, package `dresscode`, entry point `dresscode = "dresscode.cli:main"`, runtime deps `typer` and `rich`, dev deps `pytest`, `ruff`, `ty`, `pre-commit`; `.python-version` pin.
- [ ] 1.2 Package skeleton `dresscode/{__init__,cli,config,entries,repo,diff,run,harness,gate,report,context}.py`; `cli.py` exposes a `typer` app whose commands exist and exit `2` as unimplemented.
- [ ] 1.3 Test scaffolding: `testpaths = ["dresscode"]`, colocated `test_*.py`, a `git_repo` fixture building a real temporary repository with a base branch and a feature branch, and an `xdg_home` fixture pointing `XDG_STATE_HOME`/`XDG_CONFIG_HOME` at a temp dir so no test touches the real store.
- [ ] 1.4 Test: `dresscode --help` exits `0` and lists every planned command.

## 2. Repository identity, configuration layers and entries

- [ ] 2.1 Implement `repo.py`: identity from the normalized `origin` URL, fallback to the main worktree realpath, identical from a linked worktree; exit `2` outside a git work tree.
- [ ] 2.2 Implement `config.py`: load and merge the three layers (private per-repo, repository-local file or directory, global), scalars overriding, missing layers tolerated, invalid TOML exiting `2` with the file named.
- [ ] 2.3 Implement `entries.py`: entry parsing with required `id`/`question`/`expects`, optional `reveal`/`context`/`enabled`, unknown keys rejected, merge by `id`, `enabled = false` dropping an entry.
- [ ] 2.4 Implement the counter store in the global store, independent of the configuration layers.
- [ ] 2.5 Implement `dresscode add --layer` and `dresscode retire <id> --reason`.
- [ ] 2.6 Tests: two clone URL shapes resolving equal; worktree identity; each layer winning in turn; missing required key and unknown key errors; merge and disable; counters updating with a read-only repository layer; `add` round-tripping into `list`.

## 3. Diff scope

- [ ] 3.1 Implement base ref resolution with the configured → `origin/HEAD` → `main`/`master` → root commit chain, reporting the resolved base.
- [ ] 3.2 Implement the scoped diff: `git diff --merge-base <base>` against the working tree, plus untracked non-ignored files as additions.
- [ ] 3.3 Implement `diff.exclude` with the documented defaults, applied to listing and counting.
- [ ] 3.4 Implement the fingerprint over scoped content: stable when nothing changes, different after a scoped edit, unchanged by an excluded edit.
- [ ] 3.5 Implement `dresscode diff` with `--numstat` and `--json`.
- [ ] 3.6 Tests against the real temporary repository, no mocking of git: committed plus staged plus unstaged all counted; base-moved-on case; untracked included, ignored excluded; lockfile excluded by default; the three fingerprint properties.

## 4. Run state and review cycle

- [ ] 4.1 Implement the run key (repo identity plus branch, `detached-<sha>` fallback) and JSON run state under `$XDG_STATE_HOME/dresscode/runs/`; assert in tests that the repository stays untouched.
- [ ] 4.2 Implement `harness.py`: the adapter protocol `detect() -> {harness, session_id, is_child}`, a `pi` adapter (`PI_SUBAGENT_CHILD`, `PI_SESSION_ID`), a configurable `env` adapter, and a null result when nothing matches.
- [ ] 4.3 Implement implementer identity capture on `check`/`diff`/`add`/`waive`/`report`/`reset`, and never on `list`/`attest`/`answer`.
- [ ] 4.4 Implement `dresscode attest --fresh|--same-session`: required before the first answer, `--same-session` refused under `strict` and `attested`, recorded under `off`.
- [ ] 4.5 Implement the `freshness` policy: same-session refusal under every policy but `off`; `strict` requiring a supplied distinct identity; `attested` accepting an unavailable identity and recording the downgrade.
- [ ] 4.6 Implement `dresscode list` emitting `id`, `question` and context, never `expects` or `reveal`, with `--json`.
- [ ] 4.7 Implement `dresscode answer` with required evidence, fingerprint pinning, counter updates, reveal in the response, re-answer replacing and history kept; `--n-a` never failing the gate.
- [ ] 4.8 Implement staleness against the current fingerprint, and `dresscode reset`.
- [ ] 4.9 Tests: branch switch isolating runs; detached HEAD; `list --json` containing no sealed keys; answer-before-attest refused; implementer session refused; reveal returned; empty evidence and unknown id exiting `2`; scoped edit staling a verdict while an excluded edit does not; reset clearing verdicts and keeping counters.

## 5. Verdict gate

- [ ] 5.1 Implement `dresscode check`: green condition, blocking states (`unanswered`, `stale`, `context_failed`, `violated`), the fixing command per entry, exit codes `0`/`1`/`2`, and `--json`.
- [ ] 5.2 Implement `dresscode waive`: only over a violating verdict, reason required, author and fingerprint stored, status `passed-with-waivers`, staleness like a verdict.
- [ ] 5.3 Implement `check --strict` failing on waivers and on a recorded freshness downgrade.
- [ ] 5.4 Implement `dresscode report` with `rich`: status, diff size, freshness level, per-entry verdict with evidence and reveal, waivers in their own section, no ANSI when not a TTY.
- [ ] 5.5 Tests: green run; each blocking state naming its command; usage error exiting `2` while a failing gate exits `1`; waiver flipping the gate and `--strict` flipping it back; waiver over a satisfied entry refused; report content and non-TTY plainness.

## 6. Context commands

- [ ] 6.1 Implement context execution from the repository root with captured stdout, an output cap with a truncation marker, and `context.timeout_seconds` (default `10`).
- [ ] 6.2 Implement the trust store: repository-local commands blocked until `dresscode trust`, trust bound to a content hash of the repository-local layer, private and global layers always trusted.
- [ ] 6.3 Implement `context_failed` on non-zero exit or timeout, with the stderr tail surfaced and `check` blocking.
- [ ] 6.4 Implement recording the context output into the run state and showing it in `report`.
- [ ] 6.5 Tests: untrusted clone runs nothing and names `dresscode trust`; trust granted then invalidated by an edit; failing and hanging commands both landing as `context_failed`; recorded output appearing in the report; truncation marker.

## 7. Integration and packaging

- [ ] 7.1 End-to-end test over a real temporary repository with as few mocks as possible: implementer runs `check` (red) → `list` → `attest --fresh` → `answer` for every entry including one violation → `waive` → `check` green with `passed-with-waivers` → `check --strict` red → `report` showing the waiver; then edit a file and assert the verdicts go stale.
- [ ] 7.2 End-to-end test of the freshness refusal: the same session identity that ran `check` is refused at `attest` and at `answer`.
- [ ] 7.3 `uv tool install .` from the repo, run `dresscode check` in a real project, confirm the store lands under `$XDG_STATE_HOME` and the repository is untouched.
- [ ] 7.4 Add `.pre-commit-config.yaml` (`ruff-format`, `ty`) and document the `dresscode check` hook.
- [ ] 7.5 Write the README install and usage sections (`uv tool install .`, `uv tool install --force --refresh .`, `uv run dresscode`), the three configuration layers, an example entry with a context command, and the exit-code table.
