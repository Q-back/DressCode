# Spec Delta

## ADDED Requirements

### Requirement: Verdicts expire with the reviewed commit

The system SHALL mark a verdict `stale` when the resolved `HEAD` differs from its recorded `head_commit`, and SHALL require a new answer before the gate can pass. Equality SHALL mean the same full commit ID, not matching file content. Returning to the same recorded commit within the same run SHALL restore freshness unless another existing validity rule blocks the verdict. Local edits SHALL block guarded commands under the clean-tree rule instead of receiving a fingerprint.

#### Scenario: Code changed after the review
- **WHEN** reviewed source changes are committed after every question was answered
- **THEN** `check` reports the previous verdicts as stale and exits `1`

#### Scenario: Excluded change also expires verdicts
- **WHEN** only an excluded lockfile is changed and committed after review
- **THEN** the previous verdicts are stale despite unchanged scoped counts

#### Scenario: Message-only amendment
- **WHEN** an amendment changes only the commit message and produces a different commit ID
- **THEN** previous verdicts are stale

#### Scenario: Same commit restores freshness
- **WHEN** a branch returns cleanly to the exact saved `head_commit` with the same baseline and unchanged review definitions
- **THEN** its saved verdicts are current again

## MODIFIED Requirements

### Requirement: Run identity

The system SHALL key each run by repository identity, branch name and full resolved baseline commit ID, using `detached-<short sha>` for detached `HEAD`. Ref spelling and selection method SHALL NOT distinguish runs. Different baselines SHALL keep separate verdicts, history, contexts and waivers. Returning to the same branch and baseline SHALL restore its run; saved `head_commit` values SHALL determine freshness. Commit-bound runs SHALL use a namespace separate from fingerprint-based runs.

#### Scenario: Branch switch selects another run
- **WHEN** answers are recorded on `feature-a` and the checkout moves to `feature-b`
- **THEN** `check` on `feature-b` reports every question unanswered

#### Scenario: Return to a branch
- **WHEN** the checkout returns cleanly to `feature-a` with its baseline and reviewed commit unchanged
- **THEN** the previously recorded verdicts are still current

#### Scenario: Detached HEAD
- **WHEN** `HEAD` is detached
- **THEN** the branch component derives from the commit SHA

#### Scenario: Equivalent selectors share a run
- **WHEN** default selection, a ref alias or an explicit SHA resolves to the same baseline on the same branch
- **THEN** they select the same run without a comparison-mode key

#### Scenario: Baseline changes select another run
- **WHEN** a moving ref or changed default merge base resolves to a different commit
- **THEN** a different run is selected even if its scoped content is identical

### Requirement: Recording a verdict

The system SHALL accept `dresscode answer <id> --yes|--no|--n-a --evidence <text>` with non-empty evidence. It SHALL store the verdict and evidence with the full reviewed `head_commit` and a timestamp, update entry counters, and respond with the expected answer, whether the verdict matched, and the reveal. Answering again SHALL replace the current verdict and keep the previous one in run history. Verdicts and history SHALL NOT use diff fingerprints.

#### Scenario: Evidence required
- **WHEN** `answer` runs with empty or missing `--evidence`
- **THEN** it is refused with exit `2`

#### Scenario: Reveal returned after the verdict
- **WHEN** a verdict is recorded for an entry with a reveal
- **THEN** the response contains the expectation, match result and reveal after the verdict has been saved with its `head_commit`

#### Scenario: Unknown entry
- **WHEN** `answer` names an ID that is not in the effective list
- **THEN** it is refused with exit `2`

### Requirement: Visible and reproducible scope

Successful review commands SHALL identify the baseline and reviewed commit in text and include top-level `base_commit`, `head_commit` and `run_key` in JSON. Review payloads SHALL use `head_commit` instead of `fingerprint` while retaining sealed-question behavior. Gate repair commands SHALL explicitly pin the selected baseline SHA so following them cannot accidentally act on another baseline.

#### Scenario: Recovering a blocked scoped review
- **WHEN** `check --base HEAD~2` reports an unanswered question
- **THEN** its displayed answer, list and waiver remedies include `--base` with the resolved baseline SHA, not a moving expression

#### Scenario: Successful review metadata
- **WHEN** a review command emits successful JSON
- **THEN** its metadata identifies the full baseline and reviewed commit IDs and does not expose a diff `fingerprint`

### Requirement: Legacy run safety

Neither fingerprint-based baseline runs nor older repo-and-branch runs SHALL provide approvals or context to commit-bound runs. Old files SHALL remain untouched; commit-bound runs SHALL start unanswered unless commit-bound state already exists. Shared counters, retirements and trust SHALL be retained. Rollback documentation SHALL require the downgraded CLI's `dresscode reset` per repository/branch/baseline before relying on its gate.

#### Scenario: Existing installation upgrades
- **WHEN** fingerprint-based verdicts, waivers or context exist before upgrading
- **THEN** they cannot approve a commit-bound run, their files remain intact and documentation requires a fresh review

#### Scenario: Shared state survives upgrade
- **WHEN** a repository starts its first commit-bound review
- **THEN** its existing counters, retirements and context trust remain available without importing old review approvals

## REMOVED Requirements

### Requirement: Verdicts expire with the diff

**Reason**: Content-based freshness and the excluded-change exception are replaced by exact reviewed-commit freshness.

**Migration**: Commit before review and record fresh answers whenever `HEAD` differs from the saved `head_commit`.
