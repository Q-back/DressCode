# Design

## Context

`collect(config)` serves inspection and review commands; its output currently assumes a merge-base comparison. See the proposal for motivation and the spec for behavior.

## Goals / Non-Goals

Reuse one collector without changing default callers. No ranges, two-ref comparisons, patches, fetching, persistent overrides or state migration.

## Decisions

- Only `show_diff` forwards an optional ref to `collect`. Check `is not None`: an empty argument is an error, not a default. Avoid configuration mutation or a global option, which would broaden review scope.
- Resolve once with `git rev-parse --verify --quiet --end-of-options REF^{commit}`; use the resulting commit ID in subsequent commands. Explicit mode skips configured-ref resolution and merge-base calculation, so unrelated histories work. Other configuration errors still apply.
- Reuse collection, exclusions, untracked reconciliation and submodule checks. Every diff call, including submodule fingerprint patches, uses the same baseline; exact mode omits `--merge-base`.
- Keep default output unchanged. Exact text uses `Base: REF (commit SHA)`; exact JSON adds `base_commit` and sets `merge_base: null`. Do not calculate or label an informational merge base. Numstat streams and JSON precedence stay unchanged.
- Keep content fingerprints unsalted by ref spelling or mode. Test commit stability against a fixed SHA, since expressions such as `HEAD~2` move. Explicit-ref context output remains evidence, not a review-scope override.

## Risks / Trade-offs

Two comparison modes can confuse users or regress shared consumers. Mitigate with clear help/output and real-Git tests of diverged refs, unchanged default output/fingerprints and review-state isolation.

## Migration Plan

Ship argument, collector, tests and docs together. No data migration; rollback removes only exact-ref support.
