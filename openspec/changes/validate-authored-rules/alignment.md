# Alignment

## Behavior changes

### 1. Prove that the rule distinguishes the historical cases

- **[Validation before readiness](specs/rule-authoring/spec.md#requirement-both-behavioral-controls-are-required)**:
  require detection on the offending version and acceptance of the correction.
  - Was: the skill explained how to write and add a question without testing its detection.
  - The offending DressCode gate deliberately fails with the target violation.
  - Errors, missing answers, unrelated failures and waivers do not count.

- **[Pinned historical scope](specs/rule-authoring/spec.md#requirement-reproducible-historical-cases)** *(new)*:
  compare both historical versions with one baseline from before the offending change.
  - Record full commit IDs and inspect the actual patches.
  - Checking out a pre-fix commit with an empty review diff is not a test.

- **[Removed applicability](design.md#compare-two-historical-versions-against-one-baseline)** *(new, agent decision)*:
  accept a corrected not-applicable verdict only with evidence that the correction removed applicability.
  - A generic not-applicable answer is not evidence that the rule works.

### 2. Keep reviews independent and state disposable

- **[Blind case reviewers](specs/rule-authoring/spec.md#requirement-independent-blind-reviewers)** *(new)*:
  give each case a separate fresh-context reviewer.
  - Withhold the authoring transcript, sealed fields, expected case outcome and other review.
  - The coordinator records the returned verdict unchanged before comparing outcomes.

- **[Isolated validation](specs/rule-authoring/spec.md#requirement-isolated-validation-environment)** *(new)*:
  use disposable checkouts and separate temporary config and state homes per case.
  - Worktrees alone do not isolate DressCode data.
  - Keep the candidate active without letting unrelated rules determine the result.
  - Inspect context commands before execution, including implicitly trusted commands.

- **[Revised candidates](specs/rule-authoring/spec.md#scenario-a-candidate-is-revised-after-a-failed-control)** *(new, agent decision)*:
  rerun both controls with new reviewers and clean state after changing the candidate.
  - Do not rewrite a verdict merely to match its revealed expectation.

### 3. Report proof or escalate

- **[Missing evidence](specs/rule-authoring/spec.md#requirement-escalation-instead-of-invented-cases)** *(new)*:
  stop validation and ask the user when usable history or independent review is unavailable.
  - Keep the rule unvalidated while blocked.
  - Do not silently substitute generated examples or self-review.

- **[Validation report](specs/rule-authoring/spec.md#requirement-auditable-validation-report)** *(new)*:
  report the candidate, pinned scopes, reviewer separation, verdicts, evidence and blockers.
  - One successful pair is not a claim of general detection accuracy.

## Surprises / scope changes

- **[Instruction-level enforcement](proposal.md#impact)**:
  update the existing exported skill rather than add a CLI runner or stored validation flag.
  - `dresscode add` itself will not enforce this workflow.
  - Installed skill copies are not edited automatically.

- **[Test limits](design.md#test-the-instructions-without-faking-behavioral-proof)**:
  deterministic tests exercise real Git and CLI mechanics using clearly scripted verdicts.
  - Those tests do not replace the blind historical reviews required for a real rule.
