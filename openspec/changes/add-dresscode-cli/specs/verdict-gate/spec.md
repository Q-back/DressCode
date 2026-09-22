## Purpose

Turn recorded verdicts into a decision: a machine gate that says exactly what is missing, a documented way to ship a violation anyway, and a human read-out of why the task is believed done.

## ADDED Requirements

### Requirement: Green condition

The system SHALL exit `0` from `dresscode check` when every enabled, non-retired entry has a current verdict that either matches `expects`, is `n-a`, or is covered by a current waiver.

#### Scenario: All matching

- **WHEN** every entry is answered as expected
- **THEN** `check` exits `0` and reports the run green

#### Scenario: Empty list

- **WHEN** no entries are configured
- **THEN** `check` exits `0`

### Requirement: Failure output names the fix

The system SHALL print, for each entry that blocks the gate, its id, its question, its blocking state (`unanswered`, `stale`, `context_failed`, `violated`) and the exact command that clears it, then exit `1`.

#### Scenario: Unanswered entry

- **WHEN** an entry has no verdict
- **THEN** `check` prints it as `unanswered` with the `dresscode answer <id>` command and exits `1`

#### Scenario: Unwaived violation

- **WHEN** a verdict contradicts `expects` and no waiver exists
- **THEN** `check` prints it as `violated` with both the `dresscode answer` and `dresscode waive <id> --reason` commands, and exits `1`

### Requirement: Exit codes

The system SHALL use exit code `0` for green or waived, `1` for action needed, and `2` for usage, configuration or environment errors, in every command.

#### Scenario: Usage error is distinguishable

- **WHEN** a command is invoked with an unknown entry id
- **THEN** it exits `2`, not `1`, so a hook can tell a broken invocation from a failing gate

### Requirement: Waivers

The system SHALL accept `dresscode waive <id> --reason <text>` only for an entry whose current verdict contradicts `expects`, SHALL store the reason, author identity, timestamp and the current diff fingerprint, and SHALL make `check` exit `0` with status `passed-with-waivers`. A waiver SHALL become stale exactly as verdicts do, and SHALL NOT outlive the run.

#### Scenario: Documented violation ships

- **WHEN** the size question is answered `--no` and waived with a reason
- **THEN** `check` exits `0` and reports status `passed-with-waivers`

#### Scenario: Waiving a satisfied entry

- **WHEN** `waive` targets an entry answered as expected
- **THEN** it is refused with exit `2`

#### Scenario: Reason required

- **WHEN** `waive` runs with empty or missing `--reason`
- **THEN** it is refused with exit `2`

#### Scenario: Waiver expires with the diff

- **WHEN** the diff changes after a waiver is recorded
- **THEN** the waiver is stale and the entry blocks the gate again

### Requirement: Strict gate

The system SHALL support `dresscode check --strict`, exiting `1` when the run passes only through waivers or with a recorded freshness downgrade, so CI can hold a line the local gate does not.

#### Scenario: CI rejects a waived run

- **WHEN** a run is `passed-with-waivers` and `check --strict` runs
- **THEN** it exits `1` and lists the waivers

#### Scenario: CI rejects a downgraded review

- **WHEN** the run was answered under an attested-only or disabled freshness policy
- **THEN** `check --strict` exits `1` naming the downgrade

### Requirement: Human report

The system SHALL provide `dresscode report`, printing a colored summary: overall status, the diff size, the freshness level that held, each entry with its verdict, evidence and reveal, and waivers in their own section.

#### Scenario: Report after a green run

- **WHEN** `dresscode report` runs on a green run
- **THEN** it shows every question with its verdict and evidence, and states the freshness level

#### Scenario: Waivers are visible

- **WHEN** the run passed with waivers
- **THEN** the report shows a separate waivers section with each reason

#### Scenario: Plain output when redirected

- **WHEN** output is not a TTY
- **THEN** the report contains no ANSI escape sequences

### Requirement: Machine-readable output

The system SHALL support `--json` on every command, emitting stable keys and nothing else on stdout.

#### Scenario: Check as JSON

- **WHEN** `dresscode check --json` runs on a blocked run
- **THEN** stdout is a single JSON document carrying the status and each blocking entry with its state, and the exit code is unchanged
