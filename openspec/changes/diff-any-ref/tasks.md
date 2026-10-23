# Tasks

## 1. Commit: Add exact-ref diff inspection

Ship implementation, tests, compatibility and docs together; checkboxes are not separate commits.

- [ ] 1.1 Write failing real-Git CLI tests for the spec scenarios: revision types/errors, diverged/unrelated histories, configuration precedence and output modes. Confirm failures before implementation.
- [ ] 1.2 Add the optional argument and shared collector baseline selection. Verify those tests pass, including consistent submodule patch/count baselines and unchanged default callers.
- [ ] 1.3 Add exact-mode rendering and metadata; verify text/numstat streams, JSON precedence and byte-for-byte default output compatibility.
- [ ] 1.4 Add broad integration coverage for local/untracked/ignored/excluded content, Gitlink updates, dirty rejection, fixed-baseline fingerprints and read-only inspection. Verify subsequent default `diff`, `check` and `report` preserve scope and verdicts.
- [ ] 1.5 Update CLI help, README and packaged skill; verify examples against tests, including the distinction between explicit-ref context evidence and gate scope.
- [ ] 1.6 Run `pytest`, `ruff format --check .`, `ruff check .` and `ty check` via `uv run --no-sync`, plus `openspec validate diff-any-ref --strict`. Inspect the diff and actual added-line count, commit, then complete fresh independent review and separate review-fix commits per repository instructions. Require passing checks and final `dresscode check` before hand-over.
