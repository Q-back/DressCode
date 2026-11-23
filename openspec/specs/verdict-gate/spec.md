# verdict-gate Specification

## Purpose

Turn recorded verdicts into a decision: a machine gate before final task hand-over that says exactly what is missing, a documented way to ship a violation anyway, and a human read-out of why the task is believed done.

## Requirements

### Requirement: Hand-over boundary

The system SHALL provide `dresscode check` as an explicit gate over the final cumulative diff, not individual commits. The documented workflow SHALL require `AGENTS.md` or the harness to run it successfully before the agent declares the task done. DressCode SHALL NOT install or require Git hooks, and intermediate commits SHALL NOT require current verdicts.

#### Scenario: Intermediate commits without review

- **WHEN** the agent makes multiple intermediate commits while configured entries remain unanswered
- **THEN** DressCode does not block those commits
- **AND** an explicit `dresscode check` still exits `1` until the cumulative diff has current passing verdicts or waivers

#### Scenario: Final result is gated

- **WHEN** the agent is ready to hand over the task
- **THEN** the documented workflow requires `dresscode check` to exit `0` against the complete current diff before declaring the task done

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
- **THEN** it exits `2`, not `1`, so the calling harness can tell a broken invocation from a failing gate

### Requirement: Waivers

The system SHALL accept `dresscode waive <id> --reason <text>` only for an entry whose current verdict contradicts `expects`, SHALL store the reason, timestamp and the current diff fingerprint, and SHALL make `check` exit `0` with status `passed-with-waivers`. A waiver SHALL become stale exactly as verdicts do, and SHALL NOT outlive the run.

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

The system SHALL support `dresscode check --strict`, applying all normal gate checks and additionally exiting `1` when the run passes only through waivers, so CI can hold a line the local gate does not.

#### Scenario: CI rejects a waived run

- **WHEN** a run is `passed-with-waivers` and `check --strict` runs
- **THEN** it exits `1` and lists the waivers

#### Scenario: Strict gate accepts an unwaived run

- **WHEN** every entry has a current matching or `n-a` verdict and no waivers are needed
- **THEN** both `check` and `check --strict` exit `0`

### Requirement: Human report

The system SHALL provide `dresscode report`, printing a colored summary: overall status, the diff size, each entry in a separate labeled block with its verdict, evidence and reveal, and waivers in their own section. The rule, verdict and evidence SHALL have greater visual prominence than the question and reveal.

#### Scenario: Report after a green run

- **WHEN** `dresscode report` runs on a green run
- **THEN** it shows every question with its verdict and evidence

#### Scenario: Structured report

- **WHEN** `dresscode report --json` runs
- **THEN** the output includes the overall status, diff size, per-entry verdicts with evidence and reveal, and waivers
- **AND** human-only labels, styles and layout do not change the JSON schema or stored field values

#### Scenario: Waivers are visible

- **WHEN** the run passed with waivers
- **THEN** the report shows a separate waivers section with each reason

#### Scenario: Stale waivers are identified

- **WHEN** the report contains a stale waiver
- **THEN** its reason remains visible in the waivers section and it is explicitly labeled as stale

#### Scenario: Plain output when redirected

- **WHEN** output is not a TTY
- **THEN** the report contains no ANSI escape sequences, including sequences embedded in recorded text
- **AND** rule headings, labels, separators, spacing and indentation still distinguish entries and their fields

#### Scenario: Rules are separate blocks

- **WHEN** the report contains multiple entries
- **THEN** each entry starts with an explicit `Rule:` heading containing its ID and current state
- **AND** a visible separator and blank space distinguish each block from the previous content
- **AND** long or multiline field values wrap within their block without truncation or loss of text

#### Scenario: Terminal field hierarchy

- **WHEN** the report is displayed in a terminal with styling enabled
- **THEN** rule headings and verdicts are bold and colored, and the `Evidence:` label is prominent
- **AND** evidence text uses normal contrast
- **AND** the question and reveal, including their labels, use slightly muted styling

#### Scenario: Matching verdict is compact

- **WHEN** an entry has a recorded yes/no answer that matches its expected answer
- **THEN** its verdict line displays `Verdict: yes` or `Verdict: no` without repeating the expectation

#### Scenario: Conflicting verdict includes the expectation inline

- **WHEN** an entry has a recorded yes/no answer that conflicts with its expected answer
- **THEN** its verdict line displays `Verdict: no (expected yes)` or `Verdict: yes (expected no)`
- **AND** the report does not add a separate Expected field

#### Scenario: Not-applicable verdict is compact

- **WHEN** an entry has a recorded `n-a` answer
- **THEN** its verdict line displays `Verdict: n-a` without an expected-answer annotation

#### Scenario: Verdict styling reflects meaning rather than the raw answer

- **WHEN** an entry is displayed with terminal styling
- **THEN** `passed` entries are styled as satisfied even when the answer is `no`, and `violated` entries are styled as violations even when the answer is `yes`
- **AND** stale or waived entries are visually distinguished from current satisfied entries

#### Scenario: Matching stale verdict stays green

- **WHEN** a stale recorded yes/no verdict matches its expected answer
- **THEN** its verdict is green
- **AND** the rule heading keeps a yellow `[stale]` state and the gate still treats the answer as stale

#### Scenario: Recorded evidence remains visible when stale

- **WHEN** an entry has a stale recorded verdict
- **THEN** its block still shows the recorded verdict and evidence
- **AND** the rule heading clearly identifies its stale state

#### Scenario: Unanswered entry keeps sealed fields hidden

- **WHEN** an entry has no recorded verdict
- **THEN** its block displays the question, `Verdict: unanswered` and its current state
- **AND** it does not disclose the expected answer or reveal, or invent evidence

#### Scenario: Secondary fields stay visible by default

- **WHEN** an entry has a recorded verdict and reveal
- **THEN** the report shows both the question and reveal without a verbosity flag
- **AND** recorded context output and context errors remain visible when present

### Requirement: Machine-readable output

The system SHALL support `--json` on every command, emitting stable keys and nothing else on stdout.

#### Scenario: Check as JSON

- **WHEN** `dresscode check --json` runs on a blocked run
- **THEN** stdout is a single JSON document carrying the status and each blocking entry with its state, and the exit code is unchanged
