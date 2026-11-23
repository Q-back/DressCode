# Spec Delta

## MODIFIED Requirements

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
