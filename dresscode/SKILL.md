---
name: dresscode
description: Understand and use DressCode, run diff-bound reviews before hand-over, and create effective review rules from recurring coding-agent mistakes.
---

# DressCode

DressCode turns recurring agent mistakes into yes/no review questions. Expected
answers and explanations stay sealed until a verdict is recorded. The CLI tracks
answers against the current diff; it neither launches reviewers nor proves their
independence. Use it for project-specific judgment that tests and linters miss,
not as a replacement for those checks.

## Setup

From a DressCode checkout, install with `uv tool install .` (uv and Python 3.14
required). Run subsequent commands in the target Git repository. No questions are
seeded; add rules as below. Use `dresscode <command> --help` for flags.

## Review

1. Run tests and inspect `dresscode diff --json` for the review base and scope.
   This reports paths and counts, not a code patch. Review the full cumulative
   changes: committed, staged, unstaged and non-ignored untracked files, subject
   to configured exclusions.
2. Run `dresscode list --json`. Give its questions, context evidence and the
   actual cumulative code diff to a fresh-context reviewer who has not seen the
   implementation transcript. Do not give it configuration, expected answers or
   reveals.
3. Record each verdict with `dresscode answer <id> --yes --evidence "<findings>"`;
   choose exactly one of `--yes`, `--no` or `--n-a`. Evidence is required,
   including why a question does not apply. Expected answers and explanations
   appear only after saving; do not change a verdict just to match them.
4. Resolve violations and obtain new verdicts after scoped edits. Answers and
   waivers become stale when the reviewed diff changes. For an explicitly
   accepted exception, `dresscode waive <id> --reason "<reason>"` requires a
   current violating answer.
5. Require `dresscode check` to exit 0 before hand-over; show `dresscode report`.
   Exit 1 needs review action; exit 2 means a usage, configuration, state or
   environment error. `check --strict` also rejects waivers. Intermediate commits
   do not need current answers. An empty rule list passes but reviews nothing.

Context commands run during `list`. Inspect repository-local commands before
`dresscode trust`; they run with your permissions, not in a read-only sandbox.
Untrusted, failed or timed-out context blocks the gate even if listing succeeds.

## Rules

Capture an observed, recurring mistake, not every imaginable best practice. Keep
the set small. Ask one concrete yes/no question with a clear applicability
boundary; choose `--expects true` for a wanted yes or `false` for a wanted no.
Use `--reveal` to explain the correction, not to hide essential review criteria.

```sh
dresscode add shared-builder \
  --question "When adding test setup, did you reuse an existing shared builder where suitable?" \
  --expects true \
  --reveal "Prefer the shared builder over duplicating test setup."
```

`add` writes shared repository config by default. Use `--layer private` for
personal rules in this repository or `--layer global` for cross-project defaults.
Higher layers override by ID: global < repo < private.

Good rules catch contextual mistakes such as duplicating an established helper or
missing compatibility work for another consumer. Avoid vague questions like
"Is the code good?", compound questions, or checks better enforced by a test,
formatter, linter or type checker. Optional `--context "<command>"` supplies
bounded evidence; use commands you understand and keep them read-only.
Retire obsolete or automated rules with
`dresscode retire <id> --reason "<why>"`.
