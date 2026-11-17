# Proposal

## Why

Git already identifies committed snapshots. Review those snapshots at hand-over instead of maintaining a separate content fingerprint for committed and uncommitted work.

## What Changes

- **BREAKING**: Review the cumulative diff from the selected baseline to the full resolved `HEAD` commit. Remove custom diff fingerprints and expose `head_commit` instead of `fingerprint` in review data.
- **BREAKING**: Require a clean working tree for `diff`, `list`, `answer`, `waive` and `check`. Staged changes, unstaged changes and non-ignored untracked files block them, even in excluded paths. Ignored files do not block them.
- Bind answers, waivers and cached context to the reviewed commit within the existing repository/branch/baseline scope. Every different `HEAD` needs fresh answers, including message-only amendments and commits that touch only excluded files.
- Keep `report` available when dirty. Limit its changes to commit metadata, committed diff counts and a clear warning that local edits are not covered. Preserve its existing layout, evidence, waivers and successful command exit for blocked reviews.
- Keep configuration commands, `trust` and `reset` usable when dirty.
- **BREAKING**: Start new commit-bound runs without importing fingerprint-based approvals or context. Retain old state files and shared counters, retirements and trust.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `diff-scope`: Compare two committed snapshots, enforce cleanliness for review commands and replace fingerprint output with the reviewed commit SHA.
- `review-cycle`: Record commit-bound verdicts, expire them on `HEAD` changes and isolate old fingerprint-based state.
- `context-commands`: Reuse context only for the same reviewed commit and reject evidence collected across checkout changes.
- `verdict-gate`: Require a clean committed checkout for hand-over, bind waivers to commits and keep reporting available with a minimal dirty-tree warning.

## Impact

Changes span `dresscode/diff.py`, `run.py`, `context.py`, `gate.py`, `cli.py` and `report.py`, their real-Git and subprocess tests, and the review workflow in `README.md`, `docs/manual.md` and `dresscode/SKILL.md`.

JSON consumers must use `head_commit` instead of `fingerprint`. Reviewers must commit before starting review and commit fixes before re-review. There is no dependency change, new Git hook, dirty-review escape hatch, report redesign or automatic conversion of old approvals.
