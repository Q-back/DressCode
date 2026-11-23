# Spec Delta

## ADDED Requirements

### Requirement: Clean working tree for review

`diff`, `list`, `answer`, `waive` and `check` SHALL require a clean repository before reviewing or recording state, even with no entries. Staged changes, unstaged changes and non-ignored untracked files SHALL block them regardless of `diff.exclude`, untracked-file display settings or submodule ignore settings. Ignored files SHALL NOT block them. A dirty tree SHALL cause exit `2`, name affected paths and explain how to clean it, without changing files, indexes or review state.

#### Scenario: Staged or unstaged changes
- **WHEN** a guarded command runs with staged or unstaged tracked changes
- **THEN** it exits `2` before recording review state or running context commands

#### Scenario: Untracked file
- **WHEN** a guarded command runs with a non-ignored untracked file
- **THEN** it exits `2` instead of adding that file to the reviewed diff

#### Scenario: Ignored files
- **WHEN** the only local files outside the committed snapshot are ignored by Git
- **THEN** they do not block review and are not included in its diff

#### Scenario: Exclusions do not bypass cleanliness
- **WHEN** a changed or non-ignored untracked path matches `diff.exclude`
- **THEN** it still blocks a guarded command

#### Scenario: Entire repository is checked
- **WHEN** a guarded command runs in a subdirectory and a path elsewhere in the repository is dirty
- **THEN** the dirty path blocks the command, including when untracked-file display or submodule ignore settings normally hide it

#### Scenario: Structured dirty-tree error
- **WHEN** a dirty tree blocks a guarded command with `--json`
- **THEN** stdout contains one JSON error document, stderr is empty and the exit code is `2`

#### Scenario: Non-review commands remain usable
- **WHEN** configuration commands, `trust` or `reset` run in a dirty repository
- **THEN** this cleanliness rule does not block them
- **AND** `report` remains available under its human-report contract

### Requirement: Committed diff definition

The current diff SHALL compare the selected baseline commit directly with the full resolved `HEAD` commit, not local file contents or the index. Each invocation SHALL resolve that reviewed commit once. Default selection SHALL use a merge base; explicit selection SHALL use the supplied commit, even with unrelated history. Both SHALL retain configured exclusions and committed submodule pointer changes.

#### Scenario: Uncommitted work blocks review
- **WHEN** the branch has two commits and an unstaged edit
- **THEN** review commands reject the dirty tree rather than mixing the edit into the committed comparison

#### Scenario: Identical in a clean checkout
- **WHEN** the working tree is clean and no override is supplied
- **THEN** the diff equals the committed branch diff against the merge base

#### Scenario: Base moved on
- **WHEN** the default target gains commits absent from the branch
- **THEN** those commits are excluded by merge-base selection

#### Scenario: Diverged or unrelated explicit ref
- **WHEN** the explicit ref contains a file absent from the reviewed commit, with diverged or unrelated history
- **THEN** inspection succeeds on a clean checkout and reports that file as removed

### Requirement: Read-only committed diff inspection

`diff` SHALL NOT modify configuration, repository files/indexes, review state or later invocations' selectors. It SHALL inspect the selected baseline and resolved reviewed commit without computing a custom content fingerprint.

#### Scenario: Inspection is not a scope switch
- **WHEN** an explicit diff is followed by a command without an override
- **THEN** that command uses its default selection, not the previous diff's ref

#### Scenario: Fixed baseline uses the new commit
- **WHEN** a new commit is inspected against the same fixed baseline
- **THEN** the output identifies the new `head_commit`, even if its scoped file counts are unchanged

## MODIFIED Requirements

### Requirement: Configured exclusions

The system SHALL exclude committed paths matching the configured `diff.exclude` pathspec list from listing and counting, defaulting to lockfiles, `vendor/`, snapshots, cassettes and fixture directories. Exclusions SHALL NOT relax the clean-tree requirement or preserve approvals after `HEAD` changes.

#### Scenario: Lockfile excluded by default
- **WHEN** a committed `uv.lock` change adds 900 lines and no `diff.exclude` is configured
- **THEN** those lines are absent from the counts

#### Scenario: Configured exclusion replaces the default
- **WHEN** `diff.exclude` is set explicitly
- **THEN** only the configured patterns are excluded from listing and counting

### Requirement: Diff command

`dresscode diff [REF]` SHALL show file counts, totals, the baseline and the full reviewed commit. `REF` SHALL be shorthand for `--base REF`; supplying both SHALL exit `2`. `--numstat` SHALL send descriptions to stderr. `--json` SHALL take precedence and leave stderr empty. Diff JSON SHALL contain `run_key`, `base_commit` (the only baseline field), `head_commit`, files and totals.

#### Scenario: Numstat form
- **WHEN** `dresscode diff --numstat` runs
- **THEN** stdout contains tab-separated counts and paths, with totals last

#### Scenario: Used as context
- **WHEN** an entry uses `context = "dresscode diff --numstat"`
- **THEN** its output is delivered alongside the question for the selected committed scope

#### Scenario: Default baseline metadata
- **WHEN** a diff succeeds with `--json` and no explicit or inherited override
- **THEN** it includes `run_key`, files, totals, the resolved `head_commit` and `base_commit` set to the calculated merge-base SHA
- **AND** it omits `fingerprint` and `merge_base`

#### Scenario: Exact baseline metadata
- **WHEN** a diff succeeds with `--json` and an explicit or inherited override
- **THEN** `base_commit` is the resolved SHA of that exact baseline and `head_commit` is the reviewed commit SHA
- **AND** it omits `fingerprint` and `merge_base`

### Requirement: Submodule scope

The system SHALL review committed submodule Gitlink commit-ID changes only, without recursively including internal file diffs in listing or counting. Git submodule display settings SHALL NOT change this representation. Local pointer changes SHALL require a parent commit before review.

#### Scenario: Clean pointer update
- **WHEN** a clean parent checkout commits a different submodule pointer
- **THEN** the Gitlink change is listed without expanding submodule files
- **AND** approvals for the previous parent commit are no longer current

#### Scenario: Clean uninitialized submodule
- **WHEN** a committed Gitlink change refers to an uninitialized submodule
- **THEN** its commit-ID change can be inspected without treating the parent repository as a submodule worktree

### Requirement: Dirty submodule rejection

The system SHALL reject guarded review commands when any initialized submodule has staged edits, unstaged edits, non-ignored untracked files, a pointer differing from the parent commit or a dirty nested submodule. Exclusions and Git settings that hide submodule changes SHALL NOT bypass this rule. The error SHALL exit `2`, name the path and explain how to clean the submodule and commit any parent pointer update. `report` SHALL remain available.

#### Scenario: Dirty tracked submodule content
- **WHEN** an initialized submodule has staged or unstaged edits, even with its commit pointer unchanged
- **THEN** `diff` exits `2`, names the submodule and remedies, and emits no successful diff

#### Scenario: Non-ignored untracked content
- **WHEN** a submodule has non-ignored untracked files, even when Git configuration hides them
- **THEN** `diff` exits `2` with the same actionable error

#### Scenario: Structured error
- **WHEN** a dirty submodule blocks `diff --json`
- **THEN** stdout is a single JSON error document, stderr is empty and the exit code is `2`

#### Scenario: Excluded dirty submodule
- **WHEN** `diff.exclude` matches a dirty submodule path
- **THEN** that submodule still blocks guarded review commands

#### Scenario: Ignored files
- **WHEN** a submodule has only ignored files
- **THEN** it does not block diff inspection

#### Scenario: Read-only error
- **WHEN** a dirty submodule causes an error
- **THEN** no files or indexes are modified, no submodule is reset or automatically excluded, and Git commits remain unrestricted

#### Scenario: Dirty nested submodule
- **WHEN** an initialized submodule contains a dirty nested submodule
- **THEN** `diff` exits `2` naming the enclosing submodule

## REMOVED Requirements

### Requirement: Current diff definition

**Reason**: The working-tree comparison is replaced by the committed diff definition.

**Migration**: Commit intended work before review. Compare the selected baseline with the resolved `head_commit`.

### Requirement: Baseline inspection is read-only

**Reason**: The fingerprint-preservation clause is obsolete. Read-only inspection is retained by the new committed-inspection contract.

**Migration**: Use the same diff selectors on a clean checkout and consume `head_commit` instead of a content fingerprint.

### Requirement: Untracked files count as additions

**Reason**: Review is limited to committed snapshots; non-ignored untracked files make the tree dirty.

**Migration**: Add and commit intended files, or otherwise clean the tree, before review.

### Requirement: Diff fingerprint

**Reason**: The full reviewed commit SHA replaces custom scoped-content hashing.

**Migration**: Use `head_commit` with the selected `base_commit`. Commit before review and answer again after any different `HEAD`.
