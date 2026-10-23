# Design

## Context

The collector assumes merge-base comparison; run storage uses only repo and branch. Extending `diff` alone would let inspection, evidence and recorded answers disagree. See the proposal and three delta specs for the contract.

## Goals / Non-Goals

One resolved baseline per invocation, shared across all review consumers. No active-scope persistence, comparison-mode identity, ranges, fetching or changes to question authoring, retirement, trust or fingerprint policy.

## Decisions

- Add subcommand-local `--base REF` to `diff/list/answer/waive/check/report/reset`; `diff REF` is shorthand, not a second selector. Reject both together, including empty arguments rather than treating them as omission.
- A pure resolver selects explicit ref, inherited `DRESSCODE_BASE_COMMIT`, or the default merge base, in that order. Resolve refs safely with `rev-parse --verify --quiet --end-of-options REF^{commit}`; require one baseline. Use only its full SHA afterward, including counts, raw metadata and Gitlink patches. Unrelated explicit histories need no merge base.
- Normalize legacy `base_ref` to `merge_base_with` per config document before merging. Reject both in one document; retain normal layer precedence and configuration errors. Do not resolve unused default targets or rewrite config.
- Pass one scope value (repository, branch, baseline SHA) through collection, stores, gate and reports. Canonically encode that tuple in a versioned run key; retain detached-HEAD naming. Ref aliases share state; a changed baseline selects another run. Content edits within a run make answers stale through the existing fingerprint.
- Export the pinned SHA only into context subprocesses. Nested unqualified DressCode commands consume it before defaults; explicit child refs remain auxiliary evidence. Context caches live inside the selected run, so equal fingerprints cannot transfer evidence between baselines.
- Add top-level `run_key` and `base_commit` to review JSON; retain existing payload fields and sealed questions. Text identifies the baseline, with numstat descriptions on stderr. Keep legacy diff `base_ref`/`merge_base` as descriptive metadata, never identity; exact selection has `merge_base: null`. Gate remedies pin the full SHA with `--base`.
- Keep diff inspection free of state writes: calculating a run key must not instantiate a locking/writing store. Do not salt content fingerprints with ref spelling or selection method.

## Risks / Trade-offs

Moving refs select new runs rather than staling old runs; use the displayed SHA to pin a review across commands. Shared changes risk cross-scope approvals or evidence: test independent complete workflows, aliases, reset isolation and actual subprocess inheritance, not only mocked helpers.

## Migration Plan

Keep legacy run files untouched and use a new key namespace; their baseline cannot safely be inferred, so require fresh answers. Preserve counters, retirement and trust stores. Document the config alias and additive JSON metadata. Rollback can still read untouched old files but must require a fresh review; never treat old approvals as covering intervening edits.

Land default baseline-keyed reviews with tests/docs first, then exact-ref CLI workflows with their tests/docs. Each group leaves default review working; only the second exposes arbitrary-ref selection.
