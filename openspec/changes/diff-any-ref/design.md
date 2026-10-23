# Design

## Context

See `proposal.md` for motivation and `specs/diff-scope/spec.md` for the behavior contract. This change needs a design because the collector is shared by inspection, verdict recording, context execution, the gate and reporting, and the current output assumes every baseline is a merge base.

Today `show_diff` calls `collect(config)`. The collector resolves `base_ref`, computes its merge base with `HEAD`, and uses `git diff --merge-base` for counts, raw metadata and submodule fingerprint content. Untracked files, exclusions and content fingerprints are added by the same collector.

## Goals / Non-Goals

**Goals:** Keep one collection pipeline, make exact comparison an opt-in argument, and preserve existing callers and default output.

**Non-Goals:** No revision ranges, two-ref comparisons, patch output, automatic fetching, configuration mutation, persistent scope override or ref arguments on other review commands. No changes to review-state format or fingerprint policy.

## Decisions

### 1. Make the explicit revision local to collection

Add an optional positional `REF` to `diff`, forwarding it as an optional keyword argument to `collect`. Test for argument presence with `is not None`, so an explicitly empty string fails rather than using defaults. Do not mutate the shared configuration object or store the override.

Only `show_diff` passes the override. Existing `collect(config)` callers in `list`, `answer`, `waive`, the gate and reporting retain their merge-base behavior. Adding a global CLI option would broaden the review-scope contract and is deliberately rejected.

### 2. Resolve once, then select the actual baseline

Reuse commit-peeling resolution with `git rev-parse --verify --quiet --end-of-options REF^{commit}`. An explicit revision must identify a single commit; ranges, non-commit objects and invalid revisions are errors. Use only the resolved commit ID in subsequent Git commands, never raw user-supplied revision text.

With an override, do not resolve the unused configured `base_ref`, compute a merge base or require related history. With no override, leave default resolution and validation unchanged. Configuration parsing and unrelated configuration errors still apply.

```text
explicit REF --> resolve one commit ---------------------+
                                                        |
no REF ------> resolve configured/default base           |
                 --> merge base with HEAD --------------+--> existing collector
                                                             --> working tree
```

All Git diff calls for one collection must use the same baseline, including raw metadata and clean-submodule fingerprint patches. Keep the current default-mode arguments where possible; exact mode omits `--merge-base`. Use the existing untracked reconciliation, pathspecs, binary handling, rename policy and submodule checks rather than a second diff implementation.

### 3. Report exact comparison without inventing a merge base

Retain default text, numstat streams and JSON shape unchanged. Carry the resolved exact baseline as optional `base_commit` metadata and allow `merge_base` to be absent internally or `null` for exact mode; do not put the selected commit into a field labelled `merge_base`.

For explicit-ref JSON, expose:

- `base_ref`: the argument as supplied.
- `base_commit`: its resolved commit ID.
- `merge_base`: `null`, since no merge-base comparison was selected.
- Existing `files`, `fingerprint` and `totals`, covering the exact comparison.

Serialize `base_commit` only for explicit-ref diff output, so existing no-argument JSON equality checks and other consumers do not change. Exact-mode text describes `Base: REF (commit SHA)`; numstat still sends this description to stderr. JSON retains precedence over numstat.

A mode-aware output is preferable to computing an informational merge base: unrelated histories are valid, and a merge-base label would suggest the wrong comparison.

### 4. Preserve content fingerprints and review-state isolation

Use the existing fingerprint algorithm with metadata from the selected baseline. Do not salt it with the ref spelling or comparison mode: equivalent scoped changes can have equal fingerprints. Stability across staging and committing is tested against a fixed commit ID, since symbolic expressions such as `HEAD~2` can resolve differently after a commit.

Exact inspection does not write state or authorize a different review scope. A context command explicitly containing a ref remains only that command's evidence; it does not rebind verdicts or the hand-over gate. Document that distinction in the README and packaged skill.

## Risks / Trade-offs

- Different explicit and default semantics can surprise users. Mitigation: show both modes in help, README examples and output metadata; test `diff main` against `diff` after `main` advances.
- Shared collection changes could alter default fingerprints or verdict staleness. Mitigation: keep default callers unchanged and run the existing diff, workflow, gate, report and context suites alongside real-Git explicit-ref regressions.
- A valid argument could accidentally fall through to a broken configured default. Mitigation: branch on argument presence before default resolution and test an unresolvable configured ref.
- Optional metadata could leak into existing JSON. Mitigation: assert the entire no-argument payload remains unchanged and test exact-mode metadata separately.
- Submodule patches could use a different baseline than counts. Mitigation: route all diff arguments through the same selected baseline and test exact-mode clean pointers and dirty rejection.

## Migration Plan

No configuration or stored-state migration is needed. Ship the CLI argument, shared collector change, tests and usage documentation together in one commit-sized outcome. Rollback removes the optional argument and exact-mode path without rewriting existing review data.
