# review-cycle Specification

## Purpose

Run one review: identify the run, hand sealed questions to the reviewer, record verdicts against the diff they were given, and expire them when the diff moves.

## Requirements

### Requirement: Run identity

The system SHALL key a run by repository identity and branch name, using `detached-<short sha>` when `HEAD` is detached. Switching branches SHALL select a different run; returning to a branch SHALL restore its run.

#### Scenario: Branch switch selects another run

- **WHEN** answers are recorded on `feature-a` and the checkout moves to `feature-b`
- **THEN** `check` on `feature-b` reports every question unanswered

#### Scenario: Return to a branch

- **WHEN** the checkout returns to `feature-a` with its diff unchanged
- **THEN** the previously recorded verdicts are still current

#### Scenario: Detached HEAD

- **WHEN** `HEAD` is detached
- **THEN** the run key derives from the commit sha rather than a branch name

### Requirement: Run state is global

The system SHALL store run state under `$XDG_STATE_HOME/dresscode/runs/` (defaulting to `~/.local/state`) and SHALL never write run state inside the repository.

#### Scenario: Nothing written into the repository

- **WHEN** a full review is recorded
- **THEN** `git status` in the repository is unchanged

### Requirement: Question delivery

The system SHALL emit from `dresscode list` every enabled, non-retired entry as `id`, `question` and its context output, with `--json` for the structured form, and SHALL NOT emit the expectation or reveal.

#### Scenario: Questions delivered with context

- **WHEN** an entry has a context command
- **THEN** its recorded output accompanies the question in `list`

#### Scenario: Retired entry absent

- **WHEN** an entry has been retired
- **THEN** it does not appear in `list`

### Requirement: Recording a verdict

The system SHALL accept `dresscode answer <id> --yes|--no|--n-a --evidence <text>` with non-empty evidence, store the verdict and evidence with the current diff fingerprint and a timestamp, update the entry counters, and respond with the expected answer, whether the verdict matched, and the reveal. Answering again SHALL replace the current verdict and keep the previous one in the run history.

#### Scenario: Evidence required

- **WHEN** `answer` runs with empty or missing `--evidence`
- **THEN** it is refused with exit `2`

#### Scenario: Reveal returned after the verdict

- **WHEN** a verdict is recorded for an entry with a reveal
- **THEN** the response contains the expectation, the match result and the reveal text

#### Scenario: Unknown entry

- **WHEN** `answer` names an id that is not in the effective list
- **THEN** it is refused with exit `2`

### Requirement: Not-applicable verdict

The system SHALL treat `--n-a` as a valid verdict that never fails the gate, requires evidence like any other, and increments the `n_a` counter rather than `violated`.

#### Scenario: Language mismatch

- **WHEN** a Python-specific question is answered `--n-a --evidence "diff touches only TypeScript"`
- **THEN** `check` treats the entry as satisfied and the `n_a` counter increments

### Requirement: Verdicts expire with the diff

The system SHALL mark a verdict `stale` when the current diff fingerprint differs from the one stored with it, and SHALL require a new answer before the gate can pass.

#### Scenario: Code changed after the review

- **WHEN** every question is answered and a reviewed source file is then edited
- **THEN** `check` reports the affected verdicts as stale and exits non-zero

#### Scenario: Excluded change keeps verdicts current

- **WHEN** only an excluded lockfile changes after the review
- **THEN** the verdicts stay current

### Requirement: Resetting a run

The system SHALL provide `dresscode reset`, discarding the current run's verdicts and waivers while preserving entry counters.

#### Scenario: Start a review again

- **WHEN** `dresscode reset` runs after a completed review
- **THEN** `check` reports every question unanswered and the counters keep their previous values
