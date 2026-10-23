## MODIFIED Requirements

### Requirement: Base ref resolution

`dresscode diff [REF]` SHALL prefer explicit `REF`; otherwise use configured `base_ref`, `origin/HEAD`, local `main`, local `master`, then the root commit. An invalid selected ref SHALL exit `2`, not fall back. Output SHALL identify the selected ref.

#### Scenario: Configured base wins
- **WHEN** no argument is supplied, `base_ref = "origin/develop"` and `origin/HEAD` exists
- **THEN** the selected base is `origin/develop`

#### Scenario: Fallback chain
- **WHEN** no argument or configured base exists, `origin/HEAD` is absent and local `main` exists
- **THEN** the selected base is `main`

#### Scenario: Repository with a single branch and no remote
- **WHEN** no argument is supplied and no configured, remote or default-branch candidate exists
- **THEN** the selected base is the root commit

#### Scenario: Explicit argument overrides configuration
- **WHEN** `dresscode diff HEAD~2` runs with a valid or unresolvable configured `base_ref`
- **THEN** it uses `HEAD~2` without resolving the unused default

### Requirement: Current diff definition

The default diff SHALL compare the merge base of `HEAD` and the selected base with the working tree. Explicit-ref `diff` SHALL instead compare the resolved commit directly, without requiring common history. Both modes SHALL retain committed, staged, unstaged and untracked scope, ignored-file handling, exclusions and submodule safety.

#### Scenario: Uncommitted work is part of the review
- **WHEN** the branch has two commits and an unstaged edit
- **THEN** all three appear in the default diff

#### Scenario: Identical in a clean checkout
- **WHEN** the working tree is clean and no argument is supplied
- **THEN** the diff equals the committed branch diff against the merge base

#### Scenario: Base moved on
- **WHEN** the base gains commits absent from the branch and no argument is supplied
- **THEN** those commits are excluded by merge-base comparison

#### Scenario: Diverged or unrelated explicit ref
- **WHEN** the explicit ref contains a file absent from the working tree, with diverged or unrelated history
- **THEN** inspection succeeds and reports the file as removed

#### Scenario: Existing scope rules apply
- **WHEN** an explicit-ref diff encounters local changes, ignored/excluded files or submodules
- **THEN** existing inclusion, exclusion, Gitlink-only and dirty-submodule rejection rules apply

### Requirement: Diff command

The system SHALL provide `dresscode diff [REF]` with file counts, totals, `--numstat`, `--json` and context-command support. Omitting `REF` SHALL preserve existing output and fingerprints. Explicit output SHALL identify the exact baseline. Numstat SHALL keep descriptions on stderr; JSON SHALL take precedence and leave stderr empty.

#### Scenario: Numstat form
- **WHEN** `dresscode diff --numstat` runs
- **THEN** stdout contains tab-separated counts and paths, with totals last

#### Scenario: Used as context
- **WHEN** an entry uses `context = "dresscode diff --numstat"`
- **THEN** its output is delivered alongside the question

#### Scenario: Exact-ref output
- **WHEN** an explicit-ref diff succeeds
- **THEN** text identifies the ref and resolved commit, not a merge base
- **AND** JSON contains the supplied `base_ref`, resolved `base_commit`, `merge_base: null` and existing files, totals and fingerprint fields

#### Scenario: No-argument JSON compatibility
- **WHEN** `dresscode diff --json` runs without a ref
- **THEN** its existing payload remains unchanged, including resolved `merge_base` and no `base_commit` field

## ADDED Requirements

### Requirement: Explicit revision validation

Explicit `REF` SHALL resolve to one commit. Invalid, empty, ambiguous, non-commit or range values SHALL exit `2` without fallback or successful output. Revision text SHALL NOT be interpreted as Git options.

#### Scenario: Supported single-commit revisions
- **WHEN** a valid branch, remote-tracking ref, lightweight/annotated tag, full/unambiguous abbreviated commit ID or `HEAD~2` is supplied
- **THEN** its resolved commit is the baseline

#### Scenario: Invalid revision
- **WHEN** an invalid value is supplied, including a blob/tree ID, range or option-like value after `--`
- **THEN** the command exits `2` with a revision error, without executing Git options
- **AND** `--json` emits one error document on stdout with empty stderr

### Requirement: Exact-ref inspection does not change review scope

Explicit-ref inspection SHALL NOT modify configuration, repository files/indexes, review state or later commands' baselines. Other review commands SHALL retain default scope. Exact-ref fingerprints SHALL retain existing content-based behavior for a fixed baseline.

#### Scenario: Inspection leaves review state and defaults unchanged
- **WHEN** explicit inspection is followed by default `diff`, `check` or `report`
- **THEN** files, indexes, configuration and review state remain unchanged, and default scope and current answers are preserved

#### Scenario: Fixed explicit baseline preserves content fingerprint behavior
- **WHEN** inspected content is staged and committed against a fixed commit ID
- **THEN** its fingerprint stays stable; excluded edits do not change it, but scoped edits do
