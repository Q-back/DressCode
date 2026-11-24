# Design

## Context

See `proposal.md` for motivation. `dresscode/diff.py` currently combines a working-tree diff, untracked-file collection and custom content hashing. The resulting fingerprint flows through verdicts, waivers, context records and JSON output. Runs already separate repository, branch and baseline identity.

`check` and `report` share `gate.review()`. Cleanliness must therefore be an explicit command policy, not an unconditional restriction inside shared diff collection or reporting.

## Goals / Non-Goals

**Goals:** Use Git's committed objects as the review snapshot, keep existing baseline isolation, and remove the custom working-content collection path.

**Non-Goals:** No dirty-review option, alternate tree hash, approval migration, new historical-report mode, report layout changes or changes to configuration trust hashing. Git's normal tracked-file semantics define cleanliness; ignored files are not part of the snapshot guarantee.

## Decisions

### 1. Carry the two resolved commits through one scope

Add `head_commit` to `ResolvedScope` and its metadata. Resolve full `HEAD` once, use it to calculate the default merge base, and pass both full SHAs to Git for collection. Preserve explicit-baseline selection and `DRESSCODE_BASE_COMMIT` inheritance.

`ScopedDiff` no longer needs `fingerprint`. Collect paths and counts from the two committed objects, retaining existing exclusion, binary, rename and Gitlink representation rules. Remove the untracked-content and fingerprint code rather than retaining a dormant dirty-review path.

Do not store a symbolic `HEAD` or branch name as the freshness token: those can move. Do not replace the fingerprint with a tree hash: that would retain content-equivalence policy when the agreed contract is an exact reviewed commit.

### 2. Keep run identity and freshness separate

Use a new `v3` run-key namespace with the existing repository/branch/baseline tuple. Do not add `head_commit` to that key. Store `head_commit` on verdicts, history, waivers and context records, replacing `fingerprint` in their validation and serialization.

This keeps previous answers visible as stale after a commit instead of selecting an empty run on every commit. The baseline remains part of run identity, so identical `HEAD` values cannot share evidence across different comparisons. Existing entry/context validity checks still apply.

Keep hashes used for state filenames, repository identifiers and context trust; only custom diff-content hashing is removed.

### 3. Enforce cleanliness at guarded command boundaries

Use one repository-wide Git status check for `diff`, `list`, `answer`, `waive` and `check`, before running context or modifying review state. It must run even when `list` has no contextual entries or the gate has no entries.

Request NUL-delimited status, all non-ignored untracked files and visible submodule changes explicitly. Use Git's `--no-optional-locks` so status does not refresh the index. Do not apply `diff.exclude` to this check. Reuse submodule validation only as needed to detect initialized or nested dirtiness independently of ignore settings; remove its exclusion bypass. Handle paths as data, including unusual names.

Keep this policy out of the global CLI callback and out of committed diff collection. Otherwise `report`, `reset` and rule management would become unnecessarily unavailable. Dirtiness is an environment error (`2`), not a stale fingerprint or a permission to auto-commit, stash or discard files.

### 4. Bind context to the same snapshot

Keep the existing command string, trust and baseline checks. Replace context freshness comparisons with `head_commit`. After all context commands finish, recheck that `HEAD` is unchanged and the repository is clean before saving the invocation's context results. Reject the invocation without overwriting saved context if the checkout changed.

A separate inherited head selector is unnecessary: read-only context sees the existing checkout, while the post-execution check rejects evidence collected after a visible checkout mutation. This is not a sandbox or a promise to detect transient changes that are completely undone during execution.

### 5. Give report the smallest necessary adaptation

Let `report` call the shared committed collector and verdict evaluation without the general clean-tree rejection. Before loading configuration, reuse the dirty-path scan to reject changes to `.dresscode.toml` and `.dresscode/*.toml`. This prevents local rule edits from hiding saved evidence or breaking parsing. Global and private layers are unchanged. Keep the current rule blocks, status vocabulary, evidence, context, reveal, waivers and command exit behavior.

Replace fingerprint metadata with `head_commit`, use committed counts, and add one dirty-tree warning plus JSON `working_tree_dirty`. While dirty, retain per-entry freshness relative to the current commit but set the overall report status to `failed`, so the display cannot imply that local edits passed review. A different `HEAD` uses the existing stale presentation. No new report modes or historical snapshot browser are needed.

## Risks / Trade-offs

- More reviews after content-neutral commits -> document that message-only amendments, empty commits and excluded-only commits need fresh answers. Do not add exceptions.
- A shared collector could accidentally block reports or permit dirty checks -> cover both command boundaries in real-Git CLI tests, including empty and context-free configurations.
- Shell context can change the checkout -> reject its results after a visible commit or cleanliness change; retain existing trust and bounded execution.
- Old binaries can still see retained old approvals after downgrade -> require reset and fresh review using the downgraded CLI before trusting its gate.

## Migration Plan

Ship the new run namespace and `head_commit` fields together. Do not read, rewrite or translate fingerprint-based run files. Retain shared counters, retirements and trust. Remove the old JSON `fingerprint` field instead of keeping a misleading alias.

Update `README.md`, `docs/manual.md` and the packaged `dresscode/SKILL.md` to use this sequence:

```text
implement -> test -> commit -> fresh review -> check -> hand over
                                   ^
                                   |
                              fix -> test -> commit
```

Explain the field replacement and fresh-review requirement on upgrade. On downgrade, reset each relevant review scope with the older CLI before relying on its gate; for versions without baseline support, reset each repository/branch. No dependencies, Git hooks or repository-local state are added.
