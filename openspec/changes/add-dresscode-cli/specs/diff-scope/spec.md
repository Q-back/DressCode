## Purpose

Define "the change under review" once, so the reviewer, the size question, the final hand-over gate and any CI invocation all mean the same thing, and so a verdict can be bound to the diff it was given.

## ADDED Requirements

### Requirement: Base ref resolution

The system SHALL resolve the base ref in order: the configured `base_ref`, then `origin/HEAD`, then a local default branch (`main`, then `master`), then the root commit. The resolved base SHALL be reported by `dresscode diff`.

#### Scenario: Configured base wins

- **WHEN** configuration sets `base_ref = "origin/develop"` and `origin/HEAD` exists
- **THEN** the diff is taken against `origin/develop`

#### Scenario: Fallback chain

- **WHEN** no `base_ref` is configured and `origin/HEAD` is not set, but a local `main` exists
- **THEN** the diff is taken against `main`

#### Scenario: Repository with a single branch and no remote

- **WHEN** none of the configured, remote or default-branch candidates exist
- **THEN** the diff is taken against the root commit

### Requirement: Current diff definition

The system SHALL define the current diff as the merge base of `HEAD` and the base ref compared against the **working tree**, so committed, staged and unstaged changes are all included.

#### Scenario: Uncommitted work is part of the review

- **WHEN** the branch has two commits and an unstaged edit
- **THEN** all three appear in the diff

#### Scenario: Identical in a clean checkout

- **WHEN** the working tree is clean, as in CI
- **THEN** the diff equals the committed branch diff against the merge base

#### Scenario: Base moved on

- **WHEN** the base ref gains commits that the branch does not contain
- **THEN** those commits are excluded, because the comparison starts at the merge base

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

The system SHALL provide `dresscode diff`, printing the scoped files with added and removed line counts and the resolved base ref, with `--numstat` for the machine-column form and `--json` for the structured form. It SHALL be usable as an entry's context command.

#### Scenario: Numstat form

- **WHEN** `dresscode diff --numstat` runs
- **THEN** each line carries added count, removed count and path, and the totals are printed last

#### Scenario: Used as context

- **WHEN** an entry sets `context = "dresscode diff --numstat"`
- **THEN** that output is delivered to the reviewer with the question

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

### Requirement: Outside a repository

The system SHALL exit `2` with a clear message when run outside a git repository.

#### Scenario: Not a git directory

- **WHEN** any command runs in a directory that is not inside a git work tree
- **THEN** the system prints an error saying so and exits `2`
