## MODIFIED Requirements

### Requirement: Base ref resolution

For `dresscode diff [REF]`, an explicit `REF` SHALL take precedence over configured `base_ref` and automatic defaults. Without an argument, the system SHALL resolve the base ref in order: configured `base_ref`, `origin/HEAD`, local `main`, local `master`, then the root commit. The resolved base SHALL be reported by `dresscode diff`.

#### Scenario: Configured base wins

- **WHEN** configuration sets `base_ref = "origin/develop"`, `origin/HEAD` exists and no argument is supplied
- **THEN** the selected base is `origin/develop`

#### Scenario: Fallback chain

- **WHEN** no argument or `base_ref` is configured and `origin/HEAD` is not set, but a local `main` exists
- **THEN** the selected base is `main`

#### Scenario: Repository with a single branch and no remote

- **WHEN** no argument is supplied and none of the configured, remote or default-branch candidates exist
- **THEN** the selected base is the root commit

#### Scenario: Explicit argument overrides configuration

- **WHEN** `dresscode diff HEAD~2` runs with `base_ref = "origin/develop"`
- **THEN** the selected base is `HEAD~2` rather than the configured ref

#### Scenario: Unresolvable configured default is not used with an argument

- **WHEN** configuration contains a syntactically valid `base_ref = "missing"` and `dresscode diff HEAD` runs
- **THEN** the selected base is `HEAD` and resolving the unused configured ref does not block inspection

#### Scenario: Invalid configured base still fails without an argument

- **WHEN** no argument is supplied and configured `base_ref` does not resolve to a commit
- **THEN** the command exits `2` instead of choosing an automatic fallback

### Requirement: Current diff definition

The default current diff SHALL remain the merge base of `HEAD` and the selected base ref compared against the working tree. Only `dresscode diff` with an explicit `REF` SHALL compare that exact resolved commit against the working tree without requiring or substituting a merge base. Both modes SHALL include committed, staged and unstaged differences, untracked non-ignored content, configured exclusions and existing submodule safety checks.

#### Scenario: Uncommitted work is part of the review

- **WHEN** the branch has two commits and an unstaged edit
- **THEN** all three appear in the default diff

#### Scenario: Identical in a clean checkout

- **WHEN** the working tree is clean, as in CI, and no explicit argument is supplied
- **THEN** the diff equals the committed branch diff against the merge base

#### Scenario: Base moved on

- **WHEN** the base ref gains commits that the branch does not contain and no explicit argument is supplied
- **THEN** those commits are excluded, because the comparison starts at the merge base

#### Scenario: Diverged explicit ref is compared directly

- **WHEN** an explicit branch contains a file added after it diverged from `HEAD` and the working tree lacks that file
- **THEN** the explicit-ref diff reports that file as removed rather than hiding it through merge-base comparison

#### Scenario: Unrelated explicit history

- **WHEN** the supplied ref resolves to a commit with no common ancestor with `HEAD`
- **THEN** inspection succeeds by comparing that commit directly with the working tree

#### Scenario: Explicit scope includes local work and respects exclusions

- **WHEN** an explicit-ref diff includes committed, staged, unstaged and untracked changes, an ignored file and an excluded lockfile
- **THEN** the non-ignored, non-excluded differences are counted against the supplied commit and ignored or excluded content is omitted

#### Scenario: Submodule safety applies to exact refs

- **WHEN** an explicit-ref diff encounters a dirty non-excluded initialized submodule
- **THEN** inspection exits `2` with the existing actionable submodule error

### Requirement: Diff command

The system SHALL provide `dresscode diff [REF]`, printing scoped files with added and removed line counts and the selected base ref, with `--numstat` for the machine-column form and `--json` for the structured form. It SHALL remain usable as an entry's context command. Omitting `REF` SHALL preserve existing output and default fingerprint behavior; supplying it SHALL clearly identify exact-commit comparison.

#### Scenario: Numstat form

- **WHEN** `dresscode diff --numstat` runs
- **THEN** each line carries added count, removed count and path, and the totals are printed last

#### Scenario: Used as context

- **WHEN** an entry sets `context = "dresscode diff --numstat"`
- **THEN** that output is delivered to the reviewer with the question

#### Scenario: Exact-ref text and numstat output

- **WHEN** `dresscode diff HEAD~2` runs with or without `--numstat`
- **THEN** the base description identifies `HEAD~2` and its resolved commit, without labelling it a merge base
- **AND** with `--numstat`, the description stays on stderr and stdout contains only count rows and totals

#### Scenario: Exact-ref JSON metadata

- **WHEN** `dresscode diff HEAD~2 --json` runs successfully
- **THEN** stdout contains one JSON document with `base_ref` equal to `HEAD~2`, `base_commit` equal to its resolved commit ID and `merge_base` equal to `null`
- **AND** the existing `files`, `totals` and content `fingerprint` describe the exact-ref comparison and stderr is empty
- **AND** JSON takes precedence when `--numstat` is also supplied

#### Scenario: No-argument JSON compatibility

- **WHEN** `dresscode diff --json` runs without a ref
- **THEN** its existing JSON fields and meanings remain unchanged, with a resolved `merge_base` and no additional `base_commit` field

## ADDED Requirements

### Requirement: Explicit revision validation

An explicit `REF` SHALL resolve to exactly one commit, including commit-peeling tags and single-commit revision expressions. Invalid, empty, ambiguous or non-commit values and revision ranges SHALL fail with exit `2` and no fallback. User-supplied revision text SHALL NOT be interpreted as Git options.

#### Scenario: Supported single-commit revisions

- **WHEN** the argument is a valid local branch, remote-tracking ref, lightweight or annotated tag, full or unambiguous abbreviated commit ID, or `HEAD~2`
- **THEN** the exact resolved commit is used as the comparison baseline

#### Scenario: Invalid or non-commit revision

- **WHEN** the argument is missing from the repository, empty, ambiguous, a blob or tree ID, or a range such as `HEAD~2..HEAD`
- **THEN** the command exits `2`, identifies the invalid revision and emits no successful diff

#### Scenario: Option-like revision is data

- **WHEN** an option-like revision is passed after the CLI option terminator, such as `dresscode diff -- --help`
- **THEN** it is rejected as an invalid revision without invoking Git help or treating it as a Git option

#### Scenario: Structured revision error

- **WHEN** an invalid explicit revision is supplied with `--json`
- **THEN** stdout is one JSON error document, stderr is empty and the exit code is `2`

### Requirement: Exact-ref inspection does not change review scope

An explicit-ref `diff` invocation SHALL remain read-only: it SHALL NOT change configuration, repository content or indexes, review state, or the baseline used by later invocations. Other review commands SHALL continue using the default merge-base scope. Exact-ref fingerprints SHALL retain existing content-based behavior for a fixed comparison baseline.

#### Scenario: Inspection leaves review state and defaults unchanged

- **WHEN** a review has current answers, an explicit-ref diff is inspected, and `diff`, `check` or `report` is subsequently run without an override
- **THEN** the inspection has not changed configuration, repository files, indexes or review state, and those commands still use the default scope

#### Scenario: Fixed explicit baseline preserves content fingerprint behavior

- **WHEN** scoped content is inspected against a fixed commit ID, then staged and committed without content changes
- **THEN** its exact-ref fingerprint remains unchanged
- **AND** an excluded edit leaves it unchanged while a scoped content edit changes it
