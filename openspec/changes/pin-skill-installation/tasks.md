# Tasks

## 1. Commit: Pin exported skill setup to installed source

- [ ] 1.1 Add an offline real-uv installation test using a temporary Git repository to verify resolved `direct_url.json` metadata. Add failing CLI tests for upstream pins, unrelated caller HEAD, fallback cases from the spec, and plain read-only output without Git; confirm the new behavior tests fail before implementation.
- [ ] 1.2 Implement the small metadata-based renderer from `design.md`, without dependencies or Git subprocesses. Briefly document source pinning and fallback in README and manual. Verify all skill tests, including the existing executable example, pass.
- [ ] 1.3 Run `uv run --no-sync pytest`, `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .`, `uv run --no-sync ty check`, and `openspec validate pin-skill-installation --strict`. Inspect the cumulative diff and actual added-line count, then commit the working implementation.
- [ ] 1.4 Load `agent-code-review` and obtain fresh-context, read-only review of the final cumulative diff, including unchanged fallback consumers and DressCode questions. Fix in-scope findings in separate commits and re-review. Rerun affected checks and require successful `dresscode check` before hand-over; report blockers instead of marking this complete.
