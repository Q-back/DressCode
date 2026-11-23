# Spec Delta

## MODIFIED Requirements

### Requirement: Hand-over boundary

The system SHALL provide `dresscode check` as an explicit gate over the final cumulative committed diff, not individual commits. The documented workflow SHALL require tests, a commit, fresh-context review and a successful gate before hand-over. Fixes SHALL be committed before re-review. DressCode SHALL NOT install or require Git hooks, and intermediate commits SHALL NOT require current verdicts.

#### Scenario: Intermediate commits without review
- **WHEN** the agent makes multiple intermediate commits while configured entries remain unanswered
- **THEN** DressCode does not block those commits
- **AND** an explicit `dresscode check` still exits `1` until the clean committed cumulative diff has current passing verdicts or waivers

#### Scenario: Final result is gated
- **WHEN** the agent is ready to hand over the task
- **THEN** the documented workflow requires `dresscode check` to exit `0` against the final committed snapshot before declaring the task done

### Requirement: Green condition

The system SHALL exit `0` from `dresscode check` only when the working tree is clean and every enabled, non-retired entry has a current verdict that matches `expects`, is `n-a`, or is covered by a current waiver. Freshness SHALL use the selected baseline and full reviewed commit ID. Dirty-tree errors SHALL follow the clean-tree contract even when no entries are configured.

#### Scenario: All matching
- **WHEN** the tree is clean and every entry has a current expected answer
- **THEN** `check` exits `0` and reports the run green

#### Scenario: Empty list
- **WHEN** the tree is clean and no entries are configured
- **THEN** `check` exits `0`

#### Scenario: Empty list with dirty tree
- **WHEN** the tree is dirty and no entries are configured
- **THEN** `check` exits `2` rather than passing an uncommitted snapshot

### Requirement: Waivers

The system SHALL accept `dresscode waive <id> --reason <text>` only for an entry whose current verdict contradicts `expects`. It SHALL store the reason, timestamp and full reviewed `head_commit`, and SHALL make `check` exit `0` with status `passed-with-waivers`. A waiver SHALL become stale whenever `HEAD` differs from that commit and SHALL NOT outlive its baseline-keyed run. Waivers SHALL NOT use diff fingerprints.

#### Scenario: Documented violation ships
- **WHEN** the size question has a current `--no` answer and is waived with a reason on a clean checkout
- **THEN** `check` exits `0` and reports status `passed-with-waivers`

#### Scenario: Waiving a satisfied entry
- **WHEN** `waive` targets an entry answered as expected
- **THEN** it is refused with exit `2`

#### Scenario: Reason required
- **WHEN** `waive` runs with empty or missing `--reason`
- **THEN** it is refused with exit `2`

#### Scenario: Waiver expires with the diff
- **WHEN** `HEAD` changes after a waiver is recorded, including a commit that changes only excluded files
- **THEN** the waiver is stale and the entry blocks the gate again

### Requirement: Human report

`dresscode report` SHALL show committed diff counts and commit metadata in its colored summary. It SHALL keep separate labeled rule blocks with verdicts, evidence, reveal and context, and a separate waivers section. Rule headings, verdicts and evidence SHALL be more prominent than questions and reveals. Reporting a blocked review SHALL exit `0`. A dirty tree SHALL produce a warning and overall status `failed`, not block reporting.

#### Scenario: Report after a green run
- **WHEN** `dresscode report` runs on a clean green run
- **THEN** it shows every question with its verdict and evidence

#### Scenario: Structured report
- **WHEN** `dresscode report --json` runs
- **THEN** the output includes overall status, committed diff size, full baseline and reviewed commit IDs, `working_tree_dirty`, per-entry verdicts with evidence and reveal, and waivers
- **AND** no diff `fingerprint` is emitted
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

#### Scenario: Dirty checkout remains inspectable
- **WHEN** a recorded review exists for the current commit and the working tree has local edits
- **THEN** `report` exits `0`, retains the recorded evidence and per-entry commit freshness, and warns that the edits are not covered
- **AND** its overall status is `failed`, `working_tree_dirty` is true and its diff counts exclude local edits

#### Scenario: HEAD changed after review
- **WHEN** `report` runs after a different commit becomes `HEAD` in the same run
- **THEN** it preserves recorded evidence and marks previous answers and waivers stale, using the existing report layout
