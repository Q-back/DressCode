# Changelog

Notable changes are recorded here using [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before `1.0`, patch bumps cover compatible fixes; minor bumps cover new features
or breaking changes.

## Unreleased

### Changed

- Reviews compare committed snapshots. The `diff`, `list`, `answer`, `waive`,
  and `check` commands require a clean working tree.
- Verdicts, waivers, and cached context apply to the exact reviewed commit.
  After upgrading, review again to record fresh verdicts and waivers.
- JSON output replaces `fingerprint` with `head_commit`. Reports count committed
  changes and flag local edits. Uncommitted repository rule changes block reports.

## 0.1.0 - 2026-11-16

### Added

- Review questions with expected answers, evidence, and documented exceptions.
- Diff-bound verdicts and a hand-over gate that rejects missing or stale answers.
- Review scopes for working changes, branches, commits, and exact Git refs.
- Layered configuration and shared repository identity across Git worktrees.
- Trusted context commands whose results are bound to review verdicts.
- Text and JSON reports for review results.
- An exported agent skill with installation pinned to the installed Git revision
  when supported HTTPS or SSH source metadata is available.
