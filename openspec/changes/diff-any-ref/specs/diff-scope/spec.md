## MODIFIED Requirements

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

## ADDED Requirements

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
