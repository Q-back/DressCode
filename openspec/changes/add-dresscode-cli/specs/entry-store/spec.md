## Purpose

Own the question list: how a repository is identified, which configuration layers contribute entries, what an entry carries, and which of its fields are sealed from the reviewer.

## ADDED Requirements

### Requirement: Repository identity

The system SHALL identify a repository by its normalized `origin` remote URL — scheme, credentials, trailing `.git` and trailing slash removed — falling back to the realpath of the main worktree when no `origin` remote exists. Every worktree of one clone SHALL resolve to the same identity.

#### Scenario: Origin remote present

- **WHEN** `origin` is `git@example.com:team/repo.git` in one clone and `https://example.com/team/repo` in another
- **THEN** both resolve to the same repository identity

#### Scenario: No origin remote

- **WHEN** the repository has no `origin` remote
- **THEN** the identity is the realpath of the main worktree

#### Scenario: Linked worktree

- **WHEN** a command runs inside a linked worktree of a clone
- **THEN** the identity matches the one resolved in the main worktree

### Requirement: Layered configuration

The system SHALL merge configuration from three layers, highest priority first: `~/.config/dresscode/repos/<repo_id>.toml`, the repository-local layer (`.dresscode/*.toml` when `.dresscode/` is a directory, otherwise `.dresscode.toml`), and `~/.config/dresscode/config.toml`. Every layer is optional. Scalar settings from a higher layer SHALL replace lower ones.

#### Scenario: Only the global layer exists

- **WHEN** no per-repo private file and no repository-local layer exist
- **THEN** the entries and settings come from `~/.config/dresscode/config.toml` alone

#### Scenario: Private layer wins

- **WHEN** the repository-local layer sets `freshness = "attested"` and `~/.config/dresscode/repos/<repo_id>.toml` sets `freshness = "strict"`
- **THEN** the effective policy is `strict`

#### Scenario: No configuration at all

- **WHEN** none of the three layers exist
- **THEN** commands run with no entries and default settings, and exit zero

### Requirement: Entry fields

The system SHALL read entries as an array of tables with keys `id` (string, required, unique after merging), `question` (string, required), `expects` (boolean, required), `reveal` (string, optional), `context` (string, optional shell command), and `enabled` (boolean, default `true`). Unknown keys SHALL be rejected.

#### Scenario: Minimal entry

- **WHEN** an entry declares only `id`, `question` and `expects`
- **THEN** it is loaded, `reveal` is empty, it has no context command and it is enabled

#### Scenario: Missing required key

- **WHEN** an entry omits `expects`
- **THEN** the system reports a configuration error naming the entry `id` and the missing key, and exits `2`

#### Scenario: Unknown key

- **WHEN** an entry declares `severity = "high"`
- **THEN** the system reports a configuration error naming the unknown key, and exits `2`

### Requirement: Entries merge by id

The system SHALL merge entries across layers by `id`, a higher layer overriding the fields it declares and leaving the rest intact. An entry set to `enabled = false` in a higher layer SHALL be dropped from the effective list.

#### Scenario: Field override

- **WHEN** the global layer defines entry `test-factory` and the repository-local layer redeclares it with a different `question`
- **THEN** the effective entry keeps the global `expects` and `reveal`, and uses the repository-local `question`

#### Scenario: Local disable

- **WHEN** `~/.config/dresscode/repos/<repo_id>.toml` sets `enabled = false` for an entry defined in the repository-local layer
- **THEN** the entry is absent from `list`, from `check` and from `report`

### Requirement: Sealed fields

The system SHALL NOT emit `expects` or `reveal` from `dresscode list` in any output format. They SHALL appear only in the response of `dresscode answer`, after the verdict has been recorded, and in `dresscode report` for entries already answered.

#### Scenario: List hides the expectation

- **WHEN** `dresscode list --json` runs with entries present
- **THEN** no object contains an `expects` or `reveal` key

#### Scenario: Answer reveals

- **WHEN** a verdict is recorded with `dresscode answer`
- **THEN** the response states the expected answer, whether the verdict matched, and the `reveal` text when present

### Requirement: Malformed configuration rejected

The system SHALL abort with exit code `2` and a message naming the file and the parse failure when a configuration layer exists but is not valid TOML.

#### Scenario: Invalid TOML

- **WHEN** `.dresscode/rules.toml` contains a syntax error
- **THEN** the system prints an error naming that file and the failure, and exits `2`

### Requirement: Entry authoring commands

The system SHALL provide `dresscode add` to append an entry to a chosen layer (`--layer repo|private|global`, default `repo`) and `dresscode retire <id> [--reason <text>]` to mark an entry retired. A retired entry SHALL NOT be asked, and SHALL remain readable in history with its reason.

#### Scenario: Add writes to the repository layer

- **WHEN** `dresscode add` runs with no `--layer`
- **THEN** the entry is written to the repository-local layer and appears in the next `dresscode list`

#### Scenario: Retire removes from the asked set

- **WHEN** `dresscode retire test-factory --reason "now an ast-grep rule"`
- **THEN** the entry no longer appears in `list` and the reason is stored with it

### Requirement: Per-entry counters

The system SHALL keep `asked`, `violated`, `n_a` and `last_violated` per entry in the global store, never in a configuration layer, and SHALL update them when a verdict is recorded.

#### Scenario: Violation counted

- **WHEN** an answer contradicts `expects`
- **THEN** `violated` increments and `last_violated` is set to the current timestamp

#### Scenario: Counters survive a read-only configuration

- **WHEN** the repository-local layer is read-only
- **THEN** recording a verdict still succeeds and the counters are updated in the global store
