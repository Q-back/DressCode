# context-commands Specification

## Purpose

Let an entry carry deterministic evidence: a read-only command whose output reaches the reviewer with the question, so "Are the added lines under 400?" is a judgement over real numbers rather than a guess — without letting a cloned repository run arbitrary code unasked.

## Requirements

### Requirement: Context command execution

The system SHALL run an entry's `context` command through the shell, from the repository root, when `dresscode list` builds that entry, and SHALL attach its trimmed stdout to the question.

#### Scenario: Output reaches the reviewer

- **WHEN** an entry sets `context = "dresscode diff --numstat"`
- **THEN** `list` shows the question together with that command's output

#### Scenario: Entry without a context command

- **WHEN** an entry has no `context`
- **THEN** the question is listed with no context section and nothing is executed

### Requirement: Repository-local commands require trust

The system SHALL refuse to run context commands originating from the repository-local layer until `dresscode trust` has been run for that repository, and SHALL re-require it when the repository-local layer's content hash changes. Commands from the private per-repo and global layers SHALL always run.

#### Scenario: Untrusted clone

- **WHEN** a repository with `.dresscode/` context commands is listed before being trusted
- **THEN** no command runs, the affected entries are marked `context_untrusted`, and the output names `dresscode trust`

#### Scenario: Trust granted

- **WHEN** `dresscode trust` has been run and the layer is unchanged
- **THEN** the commands run normally

#### Scenario: Layer changed after trust

- **WHEN** a trusted repository's `.dresscode/` content changes
- **THEN** trust is withdrawn and `dresscode trust` is required again

#### Scenario: Global layer is trusted implicitly

- **WHEN** a context command comes from `~/.config/dresscode/config.toml`
- **THEN** it runs without a trust prompt

### Requirement: Failure and timeout are visible

The system SHALL mark an entry `context_failed` when its command exits non-zero or exceeds the timeout (`context.timeout_seconds`, default `10`), SHALL include the captured stderr tail in the output, and SHALL make `check` block on that entry rather than letting it pass unnoticed.

#### Scenario: Command exits non-zero

- **WHEN** a context command fails
- **THEN** the entry is reported `context_failed` and `check` exits `1`

#### Scenario: Command hangs

- **WHEN** a context command exceeds the timeout
- **THEN** it is terminated, the entry is reported `context_failed`, and the timeout is named in the message

### Requirement: Context output is recorded

The system SHALL store the context output used for an entry in the run state when a verdict is recorded, and `dresscode report` SHALL show it, so a human sees the evidence the reviewer actually had.

#### Scenario: Report shows what the reviewer saw

- **WHEN** an entry with a context command is answered and `dresscode report` runs
- **THEN** the report shows the recorded context output next to the verdict

#### Scenario: Large output is capped

- **WHEN** a context command emits more than the capture limit
- **THEN** the stored output is truncated with an explicit truncation marker
