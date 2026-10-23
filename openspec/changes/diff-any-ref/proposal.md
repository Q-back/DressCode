# Proposal

## Why

Inspecting an exact revision should not require configuration edits or silently compare from its merge base.

## What Changes

- Add `dresscode diff [REF]`: compare an explicit commit, tag, branch or single-commit expression directly with the working tree.
- Without `REF`, preserve configured `base_ref`, automatic fallbacks and merge-base behavior.
- Keep existing scope rules and other review commands unchanged. Invalid explicit refs error without fallback; output identifies the actual baseline.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `diff-scope`: Optional exact-ref inspection.

## Impact

`dresscode/cli.py`, `dresscode/diff.py`, real-Git tests, README and packaged skill. No new dependencies, configuration or state migration.
