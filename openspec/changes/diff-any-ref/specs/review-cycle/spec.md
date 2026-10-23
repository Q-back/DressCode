## MODIFIED Requirements

### Requirement: Run identity

The system SHALL key each run by repository identity, branch name and full resolved baseline commit ID, using `detached-<short sha>` for detached `HEAD`. Ref spelling and selection method SHALL NOT distinguish runs. Different baselines SHALL keep separate verdicts, history, contexts and waivers; returning to the same branch and baseline SHALL restore its run, with fingerprint-based freshness.

#### Scenario: Branch switch selects another run
- **WHEN** answers are recorded on `feature-a` and the checkout moves to `feature-b`
- **THEN** `check` on `feature-b` reports every question unanswered

#### Scenario: Return to a branch
- **WHEN** the checkout returns to `feature-a` with its baseline and diff unchanged
- **THEN** the previously recorded verdicts are still current

#### Scenario: Detached HEAD
- **WHEN** `HEAD` is detached
- **THEN** the branch component derives from the commit sha

#### Scenario: Equivalent selectors share a run
- **WHEN** default selection, a ref alias or an explicit SHA resolves to the same baseline on the same branch
- **THEN** they select the same run without a comparison-mode key

#### Scenario: Baseline changes select another run
- **WHEN** a moving ref or changed default merge base resolves to a different commit
- **THEN** a different run is selected even if the content fingerprint happens to match

### Requirement: Resetting a run

`dresscode reset` SHALL discard only the selected run's verdicts, contexts and waivers, preserving entry counters and other baseline runs.

#### Scenario: Start a review again
- **WHEN** the selected run is reset after a completed review
- **THEN** its questions become unanswered and counters keep their previous values

#### Scenario: Other baselines survive reset
- **WHEN** baseline A is reset
- **THEN** baseline B's answers, waivers and context remain unchanged

## ADDED Requirements

### Requirement: Shared scope selection

`diff`, `list`, `answer`, `waive`, `check`, `report` and `reset` SHALL accept `--base REF` with exact-ref semantics. Without an explicit or inherited override, they SHALL use the configured/default merge-base baseline. Each invocation SHALL resolve one baseline and use it consistently for collection, state and evidence; selectors SHALL NOT persist between invocations.

#### Scenario: Independent review cycles
- **WHEN** a review is listed, answered and checked with `--base A`, then `--base B`
- **THEN** each cycle reads and writes only its selected run, including waivers, strict checks and reports

#### Scenario: An omitted override uses defaults
- **WHEN** an explicit-scope command is followed by a command without an override
- **THEN** the latter resolves the default scope rather than a last-used scope

### Requirement: Visible and reproducible scope

Successful review commands SHALL identify the baseline in text and include top-level `base_commit` and `run_key` in JSON, retaining existing fields and sealed-question behavior. Gate repair commands SHALL explicitly pin the selected baseline SHA so following them cannot accidentally act on another scope.

#### Scenario: Recovering a blocked scoped review
- **WHEN** `check --base HEAD~2` reports an unanswered question
- **THEN** its displayed answer/list/waiver remedies include `--base` with the resolved SHA, not a moving expression

### Requirement: Legacy run safety

Legacy repo-and-branch runs without baseline identity SHALL NOT provide approvals or evidence to baseline-keyed runs. Their files SHALL remain untouched; new runs SHALL start unanswered unless baseline-keyed state already exists. Shared counters, retirement and trust records SHALL be retained.

#### Scenario: Existing installation upgrades
- **WHEN** legacy verdicts or waivers exist at upgrade
- **THEN** they cannot make a new baseline-keyed gate pass, their files remain intact and documentation explains the required fresh review
