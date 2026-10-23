# Proposal

## Why

Inspecting changes against a particular commit, tag or branch currently requires editing configuration, and even then DressCode compares from the merge base rather than the selected commit. A one-off explicit revision should compare that exact commit with the working tree without changing the normal review scope.

## What Changes

- Add an optional positional revision: `dresscode diff [REF] [--numstat] [--json]`.
- Resolve an explicit revision to one commit and compare it directly with the working tree, not with its merge base with `HEAD`.
- Accept branches, remote-tracking refs, tags, commit IDs and single-commit revision expressions such as `HEAD~2`; reject invalid revisions or values that do not resolve to a commit without falling back.
- When no argument is supplied, retain the existing configured `base_ref` and automatic fallback chain, including merge-base comparison.
- Keep exclusions, untracked-file inclusion, counts, fingerprints and submodule safety checks consistent across both modes. Identify the actual comparison baseline in output without changing existing no-argument output.
- Keep the override read-only and local to this `diff` invocation; other review commands continue using the configured scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `diff-scope`: Allow exact-revision inspection while preserving the default merge-base review scope and existing consumers.

## Impact

- `dresscode/cli.py`: Optional argument, help text and mode-aware diff output.
- `dresscode/diff.py`: Explicit-revision resolution and a shared collection path using the selected comparison baseline.
- Real-Git tests in `dresscode/test_diff*.py` and relevant submodule/workflow coverage; README and packaged `dresscode/SKILL.md` guidance.
- No new dependencies, configuration keys, review-state migration or changes to `list`, `answer`, `waive`, `check` or `report` scope.
