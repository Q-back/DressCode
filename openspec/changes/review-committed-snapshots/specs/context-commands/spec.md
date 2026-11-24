# Spec Delta

## MODIFIED Requirements

### Requirement: Scope-local context evidence

Context output and failures SHALL belong to the selected baseline-keyed run. Reuse SHALL require the same run, context command and full reviewed `head_commit`, not a content fingerprint. Trust, timeouts, output limits and failure gating SHALL remain unchanged.

#### Scenario: Evidence cannot cross baselines
- **WHEN** scope A has ready context and scope B reviews the same `head_commit` against a different baseline
- **THEN** B still needs its own context execution before its contextual answers can be recorded

#### Scenario: Report preserves scoped evidence
- **WHEN** reviews against A and B record different context outputs
- **THEN** each scoped report shows only the evidence used for that run's verdicts

#### Scenario: New commit requires new context
- **WHEN** `HEAD` changes after context was collected, even without changing scoped files
- **THEN** answers and the gate cannot reuse that context until `list` collects evidence for the new commit

## ADDED Requirements

### Requirement: Context collection stays on the reviewed commit

`list` SHALL confirm that the repository is still clean and `HEAD` still matches the resolved reviewed commit after executing context commands and before saving their results. If either check fails, it SHALL exit `2`, explain the checkout change and save none of that invocation's context results. Existing saved context SHALL remain untouched.

#### Scenario: Context command leaves local changes
- **WHEN** a context command leaves a tracked edit or a non-ignored untracked file
- **THEN** `list` rejects the invocation rather than saving its output as evidence for a clean committed snapshot

#### Scenario: Context command moves HEAD
- **WHEN** a context command creates or checks out a different commit, leaving a clean tree
- **THEN** `list` rejects the invocation and requires evidence to be collected again for the current checkout

#### Scenario: Read-only context succeeds
- **WHEN** trusted context commands finish without changing the reviewed commit or dirtying the tree
- **THEN** their bounded output is saved with the resolved `head_commit` and the existing pinned baseline
