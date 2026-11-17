# Proposal

## Why

A well-formed review question can still miss the mistake it was written to catch. The exported DressCode skill must teach agents to prove that a new rule detects a real offending change and accepts its corrected version before calling the rule validated.

## What Changes

- Extend the existing exported skill with a rule-authoring and validation workflow.
- Require historical offending and corrected cases, reviewed against one pinned baseline that exposes the relevant change.
- Use a separate blind, fresh-context reviewer for each case, with isolated DressCode configuration and state.
- Require evidence of the target violation on the offending case and a satisfied rule on the corrected case. Command errors, unrelated gate failures and waivers are not successful validation.
- Escalate to the user when usable historical cases are missing. Do not silently substitute invented examples or report the rule as validated.
- Document the workflow and test its executable CLI steps without claiming that scripted verdicts prove an agent can detect the issue.

## Capabilities

### New Capabilities

- `rule-authoring`: Instructions for writing review questions, validating them through blind historical comparisons, and reporting validation or blockers.

### Modified Capabilities

None. Existing review, baseline, configuration and gate behavior is reused without changing its CLI contracts.

## Impact

- Update `dresscode/SKILL.md`, the source exported by `dresscode --skill`.
- Update the authoring guidance in `docs/manual.md`.
- Extend `dresscode/test_skill.py` and related workflow tests as needed to exercise the documented commands with real Git repositories and isolated XDG directories.
- No new CLI command, agent runner, package dependency or persistent validation record. The calling agent or harness arranges the reviewers and reports the evidence.
- Do not edit installed skill copies outside this repository.
