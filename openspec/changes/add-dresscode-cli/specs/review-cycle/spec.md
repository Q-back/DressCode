## Purpose

Run one review: identify the run, capture who implemented it, hand sealed questions to a reviewer that is not that implementer, record verdicts against the diff they were given, and expire them when the diff moves.

## ADDED Requirements

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

### Requirement: Implementer identity capture

The system SHALL record the calling session identity as an implementer identity of the run when `check`, `diff`, `add`, `waive`, `report` or `reset` runs, and SHALL NOT do so for `list`, `attest` or `answer`. Identity comes from a harness adapter exposing `{harness, session_id, is_child}`, with a `pi` adapter reading `PI_SUBAGENT_CHILD` and `PI_SESSION_ID`, and a configurable `env` adapter for other harnesses.

#### Scenario: Implementer observed through the gate

- **WHEN** the implementing session runs `dresscode check` before requesting a review
- **THEN** its session identity is stored as an implementer identity of the run

#### Scenario: Reviewer commands do not claim implementer role

- **WHEN** a session runs only `list`, `attest` and `answer`
- **THEN** it is never recorded as an implementer identity

#### Scenario: No adapter matches

- **WHEN** no adapter can supply a session identity
- **THEN** the run records that identity was unavailable, rather than failing

### Requirement: Same-session answers are refused

The system SHALL refuse `attest` and `answer` from a session identity already recorded as an implementer of the run, under every `freshness` policy except `off`. This catches inline self-grading; it does not prove freshness, and the limitation SHALL be stated in the refusal message.

#### Scenario: Implementer tries to grade itself

- **WHEN** the session that ran `check` then runs `answer`
- **THEN** the verdict is refused with exit `1` and a message explaining that a different session must answer

#### Scenario: Policy off

- **WHEN** `freshness = "off"`
- **THEN** the answer is accepted and the run records that freshness checking was disabled

### Requirement: Attestation handshake

The system SHALL require `dresscode attest --fresh | --same-session` before the first answer of a run, recording the claim, the reviewer identity and the timestamp. `--same-session` SHALL be refused under policies `strict` and `attested`, with guidance to run the review in a fresh session, and accepted under `off` as a recorded downgrade.

#### Scenario: Answer before attestation

- **WHEN** `dresscode answer` runs on a run with no attestation
- **THEN** it is refused with exit `1` and names `dresscode attest` as the fix

#### Scenario: Honest self-declaration blocks

- **WHEN** `dresscode attest --same-session` runs under the default policy
- **THEN** it is refused with exit `1` and guidance to spawn a fresh reviewer

### Requirement: Freshness policy

The system SHALL support `freshness` values `strict`, `attested` (default) and `off`. Under `strict` an answer SHALL be refused unless an adapter supplies a reviewer identity that differs from every implementer identity. Under `attested` an answer SHALL be accepted when identity is unavailable, on the strength of the attestation alone, and the run SHALL record the downgrade.

#### Scenario: Strict without adapter identity

- **WHEN** `freshness = "strict"` and no adapter can supply an identity
- **THEN** the answer is refused with exit `1` and a message naming the missing identity source

#### Scenario: Attested without adapter identity

- **WHEN** the default policy applies and no adapter can supply an identity
- **THEN** the answer is accepted and the run is marked as attested-only

### Requirement: Question delivery

The system SHALL emit from `dresscode list` every enabled, non-retired entry as `id`, `question` and its context output, with `--json` for the structured form, and SHALL NOT emit the expectation or reveal.

#### Scenario: Questions delivered with context

- **WHEN** an entry has a context command
- **THEN** its recorded output accompanies the question in `list`

#### Scenario: Retired entry absent

- **WHEN** an entry has been retired
- **THEN** it does not appear in `list`

### Requirement: Recording a verdict

The system SHALL accept `dresscode answer <id> --yes|--no|--n-a --evidence <text>` with non-empty evidence, store the verdict with the current diff fingerprint, the reviewer identity and a timestamp, update the entry counters, and respond with the expected answer, whether the verdict matched, and the reveal. Answering again SHALL replace the current verdict and keep the previous one in the run history.

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

The system SHALL provide `dresscode reset`, discarding the current run's attestation and verdicts while preserving entry counters.

#### Scenario: Start a review again

- **WHEN** `dresscode reset` runs after a completed review
- **THEN** `check` reports every question unanswered and the counters keep their previous values
