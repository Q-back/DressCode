## ADDED Requirements

### Requirement: Context baseline inheritance

Context subprocesses SHALL receive the parent review's resolved baseline through `DRESSCODE_BASE_COMMIT`. Nested DressCode review commands SHALL prefer an explicit ref, then the inherited baseline, then configured/default selection. The inherited value SHALL be validated as a commit and SHALL NOT leak into later unrelated invocations or modify configuration.

#### Scenario: Existing diff context follows scoped review
- **WHEN** `list --base A` runs `context = "dresscode diff --numstat"`
- **THEN** that child diff compares against A, not the configured merge base, without rewriting the context command

#### Scenario: Parent baseline remains pinned
- **WHEN** a selected symbolic ref moves before a context subprocess starts
- **THEN** an unqualified child command still uses the parent's already resolved commit

#### Scenario: Explicit auxiliary context
- **WHEN** a context command explicitly requests another ref
- **THEN** that command uses its explicit ref without changing the parent review scope

### Requirement: Scope-local context evidence

Context output and failures SHALL belong to the selected baseline-keyed run. Reuse SHALL require the same run, context command and content fingerprint. Trust, timeouts, output limits and failure gating SHALL remain unchanged.

#### Scenario: Evidence cannot cross baselines
- **WHEN** scope A has ready context and scope B has the same content fingerprint
- **THEN** B still needs its own context execution before its contextual answers can be recorded

#### Scenario: Report preserves scoped evidence
- **WHEN** reviews against A and B record different context outputs
- **THEN** each scoped report shows only the evidence used for that run's verdicts
