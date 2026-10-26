# diff-scope Specification

## Purpose

Define "the change under review" once, so the reviewer, the size question, the final hand-over gate and any CI invocation all mean the same thing, and so a verdict can be bound to the diff it was given.

## Requirements

### Requirement: Base ref resolution

An explicit review ref SHALL resolve to the exact baseline commit. Otherwise the system SHALL find the merge base of `HEAD` and the first selected target: configured `merge_base_with`, `origin/HEAD`, local `main`, local `master`, then the root commit. Invalid selected refs or an unresolvable merge base SHALL exit `2`, not fall back. Output SHALL identify the resolved baseline.

#### Scenario: Configured base wins
- **WHEN** no override is supplied, `merge_base_with = "origin/develop"` and `origin/HEAD` exists
- **THEN** the baseline is the merge base with `origin/develop`

#### Scenario: Fallback chain
- **WHEN** no override or configured target exists, `origin/HEAD` is absent and local `main` exists
- **THEN** the baseline is the merge base with `main`

#### Scenario: Repository with a single branch and no remote
- **WHEN** no override or configured, remote or default-branch target exists
- **THEN** the baseline is the root commit

#### Scenario: Explicit override ignores the default target
- **WHEN** an explicit ref is supplied with a valid or unresolvable configured target
- **THEN** its exact commit is used without resolving the unused target

### Requirement: Current diff definition

The current diff SHALL compare the selected baseline commit directly with the working tree. Default selection uses a merge base; explicit selection uses the supplied commit, even with unrelated history. Both SHALL retain committed, staged, unstaged and untracked scope, ignored-file handling, exclusions, content fingerprints and submodule safety.

#### Scenario: Uncommitted work is part of the review
- **WHEN** the branch has two commits and an unstaged edit
- **THEN** all three appear in the default diff

#### Scenario: Identical in a clean checkout
- **WHEN** the working tree is clean and no override is supplied
- **THEN** the diff equals the committed branch diff against the merge base

#### Scenario: Base moved on
- **WHEN** the default target gains commits absent from the branch
- **THEN** those commits are excluded by merge-base selection

#### Scenario: Diverged or unrelated explicit ref
- **WHEN** the explicit ref contains a file absent from the working tree, with diverged or unrelated history
- **THEN** inspection succeeds and reports that file as removed

### Requirement: Untracked files count as additions

The system SHALL include untracked, non-ignored files as fully added files.

#### Scenario: New module not yet added to git

- **WHEN** a new file exists that is untracked and not ignored
- **THEN** its lines count as additions and it is listed in `dresscode diff`

#### Scenario: Ignored file

- **WHEN** an untracked file matches `.gitignore`
- **THEN** it is absent from the diff

### Requirement: Configured exclusions

The system SHALL exclude paths matching the configured `diff.exclude` pathspec list from both listing and counting, defaulting to lockfiles, `vendor/`, snapshots, cassettes and fixture directories.

#### Scenario: Lockfile excluded by default

- **WHEN** `uv.lock` changes by 900 lines and no `diff.exclude` is configured
- **THEN** those lines are absent from the counts

#### Scenario: Configured exclusion replaces the default

- **WHEN** `diff.exclude` is set explicitly
- **THEN** only the configured patterns are excluded

### Requirement: Diff command

The system SHALL provide `dresscode diff [REF]` with file counts, totals, `--numstat`, `--json` and context-command support. `REF` SHALL be shorthand for `--base REF`; supplying both SHALL exit `2`. Output SHALL identify the actual baseline. Numstat descriptions SHALL remain on stderr; JSON SHALL take precedence and leave stderr empty. Diff JSON SHALL contain `run_key`, `base_commit`, files, totals and fingerprint. `base_commit` SHALL be the only baseline field and identify the resolved comparison commit for both default and exact selection. Diff JSON SHALL NOT contain `merge_base`.

#### Scenario: Numstat form
- **WHEN** `dresscode diff --numstat` runs
- **THEN** stdout contains tab-separated counts and paths, with totals last

#### Scenario: Used as context
- **WHEN** an entry uses `context = "dresscode diff --numstat"`
- **THEN** its output is delivered alongside the question for the selected scope

#### Scenario: Default baseline metadata
- **WHEN** a diff succeeds with `--json` and no explicit or inherited override
- **THEN** it includes `run_key`, files, totals, fingerprint and `base_commit` set to the calculated merge-base SHA
- **AND** it omits `merge_base`

#### Scenario: Exact baseline metadata
- **WHEN** a diff succeeds with `--json` and an explicit or inherited override
- **THEN** `base_commit` is the resolved SHA of that exact baseline
- **AND** it omits `merge_base` rather than emitting it as `null`

### Requirement: Diff fingerprint

The system SHALL compute a fingerprint of the scoped diff, stable across invocations with an unchanged working tree, changing whenever scoped content changes, and unaffected by excluded paths. With an unchanged merge base, staging or committing unchanged scoped content SHALL NOT change the fingerprint.

#### Scenario: Stable while nothing changes

- **WHEN** the fingerprint is computed twice with no edits in between
- **THEN** both values are equal

#### Scenario: Commit boundaries do not change the reviewed result

- **WHEN** reviewed scoped content is staged and committed on the same branch without content changes or a change to the merge base
- **THEN** the fingerprint is unchanged

#### Scenario: Scoped edit changes the fingerprint

- **WHEN** a reviewed source file gains a line
- **THEN** the fingerprint differs from the previous value

#### Scenario: Excluded edit does not

- **WHEN** only an excluded lockfile changes
- **THEN** the fingerprint is unchanged

### Requirement: Submodule scope

The system SHALL review clean submodules as Gitlink commit-ID changes only, without recursively including their internal file diffs in listing, counting or fingerprinting. Git submodule display settings SHALL NOT change this representation or its fingerprint.

#### Scenario: Clean pointer update

- **WHEN** a clean submodule points to a different commit
- **THEN** the parent Gitlink change is listed and fingerprinted, without expanding submodule files
- **AND** staging or committing the unchanged pointer preserves the fingerprint when the merge base is unchanged

#### Scenario: Clean uninitialized submodule

- **WHEN** a clean submodule is uninitialized
- **THEN** its commit-ID change can still be inspected without treating the parent repository as a submodule worktree

### Requirement: Dirty submodule rejection

The system SHALL reject any non-excluded initialized submodule containing staged edits, unstaged edits, non-ignored untracked files or a dirty nested submodule before producing a diff or fingerprint. It SHALL exit `2`, name the path, and explain how to commit inside it and update the parent pointer, or explicitly exclude its path with `diff.exclude`. Git settings that hide dirtiness SHALL NOT bypass this check.

#### Scenario: Dirty tracked submodule content

- **WHEN** a non-excluded submodule has staged or unstaged edits, even with its commit pointer unchanged
- **THEN** `diff` exits `2`, names the submodule and remedies, and emits no successful diff or fingerprint

#### Scenario: Non-ignored untracked content

- **WHEN** a non-excluded submodule has non-ignored untracked files, even when Git configuration hides them
- **THEN** `diff` exits `2` with the same actionable error

#### Scenario: Structured error

- **WHEN** a dirty submodule blocks `diff --json`
- **THEN** stdout is a single JSON error document, stderr is empty, and the exit code is `2`

#### Scenario: Excluded dirty submodule

- **WHEN** `diff.exclude` matches a dirty submodule path
- **THEN** it is omitted and neither blocks the command nor affects the fingerprint

#### Scenario: Ignored files

- **WHEN** a submodule has only ignored files
- **THEN** it does not block diff inspection

#### Scenario: Read-only error

- **WHEN** a dirty submodule causes an error
- **THEN** no files or indexes are modified, no submodule is reset or automatically excluded, and Git commits remain unrestricted

#### Scenario: Dirty nested submodule

- **WHEN** an initialized submodule contains a dirty nested submodule
- **THEN** `diff` exits `2` naming the enclosing scoped submodule

### Requirement: Outside a repository

The system SHALL exit `2` with a clear message when run outside a git repository.

#### Scenario: Not a git directory

- **WHEN** any command runs in a directory that is not inside a git work tree
- **THEN** the system prints an error saying so and exits `2`

### Requirement: Default target configuration

`merge_base_with` SHALL be the only config name for the ref used to compute the default merge base, preserving normal configuration-layer precedence and configuration errors. The previous name SHALL be removed from code, tests, docs and diff JSON, without aliases, migration logic or special errors for old configs. Configuration SHALL NOT be rewritten automatically.

#### Scenario: Layer precedence
- **WHEN** a higher and lower layer both declare `merge_base_with`
- **THEN** the higher layer's target wins

### Requirement: Explicit revision validation

Explicit refs SHALL resolve to one commit using Git refname precedence. Invalid/empty refs, ambiguous abbreviated object IDs, non-commit objects and ranges SHALL exit `2` without fallback or successful output. Revision text SHALL NOT be interpreted as Git options.

#### Scenario: Supported single-commit revisions
- **WHEN** a valid branch, remote-tracking ref, lightweight/annotated tag, full/unambiguous abbreviated commit ID or `HEAD~2` is supplied
- **THEN** its resolved commit is the baseline

#### Scenario: Refname collisions
- **WHEN** a branch and tag share a name
- **THEN** Git refname precedence applies; fully qualified refs select the intended branch or tag

#### Scenario: Invalid revision
- **WHEN** an invalid value is supplied, including an ambiguous abbreviated object ID, blob/tree ID, range or option-like value after `--`
- **THEN** the command exits `2` with a revision error, without executing Git options
- **AND** `--json` emits one error document on stdout with empty stderr

### Requirement: Baseline inspection is read-only

`diff` SHALL NOT modify configuration, repository files/indexes, review state or later invocations' selectors. Fingerprints SHALL retain existing content-based behavior against a fixed baseline, independent of selector spelling.

#### Scenario: Inspection is not a scope switch
- **WHEN** an explicit diff is followed by a command without an override
- **THEN** that command uses its default selection, not the previous diff's ref

#### Scenario: Fixed baseline preserves fingerprint behavior
- **WHEN** inspected content is staged and committed against a fixed commit ID
- **THEN** its fingerprint stays stable; excluded edits do not change it, but scoped edits do
