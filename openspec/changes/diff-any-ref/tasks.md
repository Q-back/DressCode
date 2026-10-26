# Tasks

Each ordered group ships working implementation, tests, compatibility and docs together. Write tests first. At each green boundary, inspect the diff and actual added-line count, commit, then obtain fresh independent review per repository instructions; keep review-fix rounds in separate commits and re-review.

## 1. Commit: Key default reviews by their resolved baseline

Only default selection is public in this group; arbitrary-ref CLI overrides arrive in group 2.

- [ ] 1.1 Add failing real-Git tests for default resolution, `merge_base_with` configuration and layer precedence, baseline-keyed identity, equivalent baselines, moving baselines and untouched legacy runs. Verify failure before implementation.
- [ ] 1.2 Introduce shared resolved scope throughout default review consumers, versioned run keys and updated output metadata. Use only `merge_base_with` for the default target throughout code, tests and docs; remove the previous name and its diff JSON field without aliases, migration logic or special old-config errors. Pin context subprocesses via `DRESSCODE_BASE_COMMIT`. Verify existing workflows, detached HEAD, fingerprints, evidence/waiver/reset isolation, sealed questions and legacy-state safety.
- [ ] 1.3 Document `merge_base_with`, the updated diff JSON fields, scope metadata, fresh reviews and mandatory legacy reset after downgrade in README and packaged skill. Verify examples and default CLI help against tests; do not advertise unimplemented overrides.
- [ ] 1.4 Run the checks below and complete this group's commit/review boundary; verify all existing default consumers remain working before group 2.

## 2. Commit: Review exact refs across the full CLI workflow

- [ ] 2.1 Add failing tests for shared `--base REF`, positional `diff REF`, conflicts, supported/invalid revisions, diverged/unrelated histories and overridden defaults. Verify text/JSON errors, Git refname precedence, fully qualified refs, ambiguous abbreviated IDs and option-like input after `--`.
- [ ] 2.2 Expose exact-ref selection on all seven review commands and pin gate remedies to the resolved SHA. Verify aliases/default selection share runs only for equal baselines, and inspection does not change later defaults.
- [ ] 2.3 Add broad subprocess workflows reviewing two baselines, including equal fingerprints, local/untracked/excluded content, nested context inheritance, ref movement, waivers/strict gates, reports and reset isolation. Verify fixed-SHA fingerprint stability and clean/dirty submodule behavior without mocking Git.
- [ ] 2.4 Update help, README and packaged skill with complete scoped-review examples. Verify documented commands and output metadata against CLI tests.
- [ ] 2.5 Run the checks below, inspect the final cumulative changes and complete commit/review. Require final `dresscode check` success before hand-over; report blockers instead of declaring completion.

Checks for each group: `uv run --no-sync` with `pytest`, `ruff format --check .`, `ruff check .` and `ty check`; also `openspec validate diff-any-ref --strict`.
