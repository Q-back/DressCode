# Design

## Context

`dresscode/SKILL.md` is packaged and exported by `dresscode --skill`. It already covers question writing and sealed review. `dresscode/test_skill.py` runs its examples through the real CLI; `dresscode/test_scoped_workflow.py` covers pinned baselines and separate review runs.

The CLI compares a selected baseline with the working tree. A historical checkout is not itself a review scope. Linked worktrees also share repository identity, while configuration and counters can outlive individual review runs. These facts shape the isolation recipe below.

The behavior contract is in [the rule-authoring spec](specs/rule-authoring/spec.md). See [proposal.md](proposal.md) for motivation and scope.

## Goals / Non-Goals

**Goals:** Give the calling agent a reproducible procedure using existing commands, and separate evidence of rule quality from evidence that the commands work.

**Non-Goals:** Add automatic reviewer launch, enforce validation inside `add`, or create a stored `validated` flag. The calling workflow owns validation status and reports it to the user.

## Decisions

### Extend the existing standalone skill

Keep the workflow in the skill's rule-authoring section, alongside the existing question-writing guidance. Add a short manual entry pointing to the same procedure. Preserve the current authoring and exact-baseline examples and the `--skill` installation-source rendering.

A separate skill would split discovery and export without adding a new execution capability. Essential safety and acceptance instructions must remain available in the exported skill without reading the manual.

### Separate the coordinator from the case reviewers

The rule author acts as coordinator. It knows the complete candidate definition and expected case outcomes, prepares inputs, and launches one fresh reviewer for each case through the available harness. Case reviewers receive only a neutral review request, `list --json` question data, the actual scoped patch and relevant source or inspected context output. Use neutral case names; do not supply bug descriptions, fixing commit messages, authoring transcripts or expected outcomes.

Reviewers return a yes/no/not-applicable verdict and concrete evidence. The coordinator records that judgment unchanged with `answer`, then runs `check --strict` and `report`. This keeps sealed answer responses and reports out of reviewer inputs. Reviewers do not run the hand-over gate or edit the historical source. If independent contexts are unavailable, escalate rather than self-review.

### Compare two historical versions against one baseline

Resolve the offending commit, corrected commit and a baseline before the offending change to full SHAs. Confirm from the source that the first contains the mistake and the second corrects it. Use clean disposable historical worktrees or clones, without moving the user's branch or stashing their changes.

For each case, inspect `dresscode diff --base "$BASE" --json`, then obtain the actual Git patch for that baseline and the checked-out case. The JSON contains paths and counts, not a patch. Ensure exclusions do not hide the target change. Pass the same explicit baseline SHA to `diff`, `list`, `answer`, `check` and `report`; do not rely on an earlier command selecting it for later calls.

A corrected case can remove the rule's applicability, such as reverting an offending addition. A not-applicable verdict counts only with evidence of that removal, checked against the historical correction by the coordinator. An empty offending diff never proves detection.

Using only the fix commit's parent as the baseline often leaves the original mistake outside the diff. Using default branch comparisons can produce an empty diff. Neither is a substitute for inspecting the actual review scope.

### Isolate the candidate without editing historical source

Give each case its own temporary `XDG_CONFIG_HOME` and `XDG_STATE_HOME`, outside all reviewed trees. Keep these values consistent for every command in that case and its context subprocesses. Do not share case state or the user's normal state. Use the same installed DressCode executable for both cases, including nested commands; do not implicitly select a tool version from the historical checkout.

Place the complete candidate in each case's temporary private layer. Choose a new rule ID absent from both historical configs so field-wise merging cannot inherit an old command or disabled flag. Inspect historical local TOML without executing it, then use private overrides to enable the candidate and disable unrelated entries. Verify the effective list contains exactly that candidate. This avoids changing historical files or adding rule configuration to the reviewed patch. Do not copy normal global/private settings, counters, retirements or trust into the test environment.

Inspect all candidate context commands and the historical scripts they invoke before listing. Private-layer commands execute without a trust prompt, so moving a command there is not a safety review. A malformed historical config, inaccessible evidence or a hidden target diff is a blocker to resolve explicitly, not a reason to change production settings.

### Judge the target result, not just the exit code

After recording each blind verdict, the coordinator checks both the rule-level result and the command status:

| Case | Required rule result | Strict gate |
| --- | --- | --- |
| Offending version | Current `violated` verdict whose evidence identifies the target mistake | Exit `1`, caused by that violation |
| Corrected version | Current matching verdict, or justified removal of applicability | Exit `0`, with no waiver |

Capture exit `1` on the offending case as an expected test outcome, not a shell failure that skips the corrected case. Exit `2`, context errors, stale or missing answers, unrelated failures and an absent candidate do not satisfy either control. A revised candidate requires both cases to run again with new reviewer contexts and clean state; do not tune recorded answers after seeing the reveal.

Report the complete candidate definition or its version, all three SHAs, reviewer separation, per-case verdicts and evidence, gate results and blockers. Save evidence outside the reviewed trees. Remove only disposable resources created for the exercise, without forced cleanup of unexpected changes.

### Escalate when history cannot support the test

If no usable historical pair or baseline is available, explain what is missing and ask the user for refs or an explicit decision on another approach. Keep the rule unvalidated. Do not silently generate a bad/fixed fixture as a substitute or claim that one control is enough.

### Test the instructions without faking behavioral proof

Extend the executable skill-example coverage in `dresscode/test_skill.py`, reusing real Git and subprocess helpers where suitable. A deterministic test can create a temporary history, provision the documented environments, supply clearly scripted verdicts and verify the expected gate results, sealed delivery, pinned baseline and untouched normal state. Cover existing local rules so a candidate-only run is not merely assumed. Keep any new helpers local to these tests.

Those generated repositories and scripted verdicts test CLI mechanics only. They do not satisfy the historical validation required when an agent creates a real rule. Add focused checks that the exported instructions retain the independent-review, two-control and escalation requirements. For a live rule, only the separate historical review exercise supplies behavioral evidence; report it separately from unit-test results.

## Risks / Trade-offs

- **One pair can be overfit.** Report the exact evidence, not general detection accuracy. Broader evaluation is outside this change.
- **Blindness is a workflow property, not an access-control guarantee.** Keep reviewer inputs narrow and exclude sealed files and prior transcripts; do not claim the CLI enforces independence.
- **Historical commands can execute unsafe code or leak outcome hints.** Inspect dependencies and outputs before delivering context; stop when safe evidence is unavailable.
- **Fresh reviewers cost time and may disagree.** Preserve their evidence, treat a failed control as failed validation and require new contexts after revising a candidate.

## Migration Plan

Release the updated bundled skill and manual together. Users re-export `dresscode --skill` through their normal skill installation process; no automatic edits to installed copies are needed. Existing rules and run files remain unchanged. Rolling back restores the earlier instructions without a data migration.
