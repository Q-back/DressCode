---
name: dresscode
description: Review code with DressCode questions, report findings, check code changes before hand-over, and create useful review rules.
---

# DressCode

## What is DressCode

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

Use this flow when changing code or only reviewing it. If changing code, run
tests first.

1. Inspect `dresscode diff --json` for the review base and scope.
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
4. Show `dresscode report`. Every question needs an answer with evidence.
   Surface unanswered questions, stale answers, context failures and command
   errors; do not treat them as completed checks. The report command can succeed
   with status `failed`; that does not mean the code passes.

- **Changing code?** Resolve violations and obtain new verdicts after scoped
  edits. For an explicitly accepted exception, use
  `dresscode waive <id> --reason "<reason>"`; it requires a current violating
  answer. Require `dresscode check` to exit 0 before hand-over and show the final
  report. Exit 1 needs review action; exit 2 means a usage, configuration, state
  or environment error. `check --strict` also rejects waivers. Intermediate
  commits do not need current answers. An empty rule list passes but reviews
  nothing.
- **Only reviewing code?** Report the problems and stop. Do not fix the reviewed
  code or add waivers just to finish the review. `dresscode check` need not pass:
  a completed review can contain violations.

Answers and waivers become stale when the reviewed diff changes.

Context commands run during `list`. Inspect repository-local commands before
`dresscode trust`; they run with your permissions, not in a read-only sandbox.
Untrusted, failed or timed-out context blocks the gate even if listing succeeds.

## Rules

Ask one concrete yes/no question with a clear applicability boundary. Make it
answerable from the diff and available evidence, without reading the sealed
expectation or explanation. Choose `--expects true` for a wanted yes or `false`
for a wanted no. Use `--reveal` to explain the correction, not to hide essential
review criteria.

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
