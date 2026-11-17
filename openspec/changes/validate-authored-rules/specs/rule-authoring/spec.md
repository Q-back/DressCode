# Spec Delta

## Purpose

Guide agents in writing useful DressCode review questions and proving their behavior with independent reviews of real historical changes before reporting them as validated.

## ADDED Requirements

### Requirement: Self-contained rule-authoring guidance

The exported DressCode skill SHALL instruct agents to write one concrete yes/no question with an explicit applicability boundary and enough visible criteria to answer without sealed fields. It SHALL distinguish rules needing project judgment from checks better enforced by deterministic tools, explain expectation polarity, and keep essential criteria out of the reveal.

#### Scenario: Author a question from a recurring mistake

- **WHEN** an agent uses the exported skill to turn a recurring mistake into a rule
- **THEN** the guidance covers the question, applicability, expected answer, corrective reveal and destination layer
- **AND** it requires validation before the agent calls the rule validated

### Requirement: Reproducible historical cases

The skill SHALL require historical offending and corrected versions and one pinned baseline from before the offending change. It SHALL require full commit IDs, actual scoped patches and enough surrounding code to judge the rule. The offending patch SHALL expose the target mistake; checking out a commit without a relevant comparison SHALL NOT count as validation.

#### Scenario: A default comparison hides the mistake

- **WHEN** checking out the offending commit makes the default review diff empty or omits the offending change
- **THEN** the agent selects and pins a suitable earlier baseline instead of treating the empty comparison as a test
- **AND** it uses that same baseline throughout both case reviews

### Requirement: Independent blind reviewers

The skill SHALL require a separate fresh-context reviewer for each case. Reviewers SHALL receive neutral case instructions, the listed question, scoped patch and relevant code or approved context evidence, but not the authoring transcript, expected answer, reveal, case outcome label or the other review. The calling workflow SHALL arrange independence rather than claim the CLI verifies it.

#### Scenario: Reviewing the historical pair

- **WHEN** the calling workflow prepares the two case reviews
- **THEN** each reviewer starts without the rule author's conversation or the other case's verdict
- **AND** the workflow withholds sealed configuration and the expected result until that reviewer's verdict and evidence are recorded

### Requirement: Isolated validation environment

The skill SHALL require disposable checkouts and separate temporary DressCode config and state homes for each case. The same candidate rule SHALL be active in both, and unrelated rules SHALL NOT determine validation. Context commands SHALL be inspected before execution, including commands in implicitly trusted layers. Validation SHALL preserve the user's checkout, configuration and review state.

#### Scenario: Linked worktrees share repository identity

- **WHEN** the two cases use linked worktrees of one repository
- **THEN** the workflow also isolates their DressCode config and state rather than relying on worktree separation alone
- **AND** recording validation answers does not change the user's normal counters, retirements, trust or review answers

#### Scenario: Historical configuration carries other rules

- **WHEN** a case contains repository-local DressCode rules
- **THEN** the workflow ensures that the candidate is active and unrelated rules do not determine its result
- **AND** it does not execute historical context commands without inspection

### Requirement: Both behavioral controls are required

The skill SHALL permit a rule to be reported as validated only when the offending case produces a current violating verdict identifying the target mistake and the corrected case produces a current satisfied verdict with evidence of the correction. The workflow SHALL compare the recorded judgments with the expected outcomes; running commands alone SHALL NOT establish detection.

#### Scenario: Both cases behave as intended

- **WHEN** the offending case identifies the target violation and the corrected case accepts the correction
- **THEN** both validation checks pass even though the offending case deliberately fails the DressCode gate

#### Scenario: A technical failure resembles detection

- **WHEN** the offending case fails because of unanswered questions, stale answers, missing context, a command error or another rule
- **THEN** the agent does not count that failure as detection of the target mistake

#### Scenario: A corrected case passes without meaningful review

- **WHEN** the corrected case passes because the candidate is absent, waived or answered not-applicable without evidence that the correction removed its applicability
- **THEN** the agent does not count it as a successful corrected-case control

#### Scenario: A candidate is revised after a failed control

- **WHEN** the agent changes the question, expectation, reveal or context after inspecting a validation result
- **THEN** it validates the revised candidate on both cases using new reviewer contexts and clean case state
- **AND** it does not rewrite an earlier verdict merely to match the revealed expectation

### Requirement: Escalation instead of invented cases

The skill SHALL require the agent to stop validation and ask the user when it cannot identify or access a usable historical pair and baseline. It SHALL report what is missing and leave the rule unvalidated. It SHALL NOT silently create a synthetic substitute, reuse the author's context as an independent review or claim success when a required reviewer is unavailable.

#### Scenario: No usable historical pair exists

- **WHEN** the agent cannot find a historical offending version and its corrected counterpart with a suitable review baseline
- **THEN** it asks the user for suitable refs or an explicit decision on how to proceed
- **AND** the rule remains unvalidated while that decision is pending

#### Scenario: Independent review cannot run

- **WHEN** the harness cannot provide the required fresh-context reviewers
- **THEN** the agent reports the blocker to the user instead of substituting self-review

### Requirement: Auditable validation report

The skill SHALL require a report naming the rule version or complete definition, pinned baseline and case commits, reviewer separation, per-case verdicts and evidence, command results, and remaining blockers. It SHALL distinguish both controls passing from a failed or blocked attempt and from deterministic tests of CLI mechanics.

#### Scenario: Report a completed validation

- **WHEN** the agent hands over a newly validated rule
- **THEN** the report lets the user reproduce the scopes and inspect why each case met its expected outcome
- **AND** it does not present one historical pair as proof of general detection accuracy
