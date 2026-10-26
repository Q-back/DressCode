# Proposal

## Why

Reviewing an arbitrary revision needs more than a different diff: questions, evidence, verdicts and the gate must agree on the same baseline without overwriting another review.

## What Changes

- Add `diff [REF]` and shared `--base REF` selection on review commands. Explicit refs select exact commits; omission uses the merge base with configured `merge_base_with` or existing automatic defaults.
- Key runs by repository, branch and resolved baseline commit. Ref aliases and default/explicit selection share a run when they resolve to the same baseline; no comparison-mode identity.
- Carry that baseline through context evidence, answers, waivers, checks, reports and resets. Show it in output; inspection never changes later defaults.
- Keep existing scoped-content, exclusion, fingerprint and submodule rules.
- **BREAKING:** rename the config setting `base_ref` to `merge_base_with` without an alias. Reject the old key with an error naming its replacement.
- **BREAKING:** legacy runs lack baseline identity and cannot safely supply approvals to new runs. Preserve their files, but require fresh answers; counters and trust remain intact. Review JSON gains scope metadata.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `diff-scope`: Explicit baseline resolution and clear default configuration.
- `review-cycle`: Baseline-keyed runs, shared selection and compatibility.
- `context-commands`: Evidence inherits the selected baseline.

## Impact

CLI, config, diff collection, run storage, context, gate/report consumers, real-Git tests, README and packaged skill. No new dependencies.
