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

If DressCode is missing, install it with
`uv tool install 'git+https://github.com/Q-back/DressCode.git'` (uv and Python
3.14 required). Run subsequent commands in the target Git repository. No questions
are seeded; add rules as below. Use `dresscode <command> --help` for flags.

## Review

Review code, record answers and report findings. Do not change the reviewed code
or add waivers. The calling workflow handles fixes and accepted exceptions.

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

- **Changing code?** Run `dresscode check` and include its result in the report.
  If it fails, report the blockers to the caller.
  Exit 1 means the gate failed; exit 2 means a usage, configuration, state or
  environment error. `check --strict` also rejects waivers.
- **Only reviewing code?** Do not run `dresscode check`. Report the findings and
  stop, even if violations remain.

Answers and waivers become stale when the reviewed diff changes. An empty rule
list passes the gate but reviews nothing.

The default baseline is the merge base with configured `merge_base_with`,
otherwise `origin/HEAD`, local `main`, local `master`, then the root commit.
Invalid configured targets fail. Successful review JSON includes `run_key` and
`base_commit`; diff JSON uses `base_commit` as its only baseline field. Text
identifies the baseline. Runs are separate per repository, branch and baseline;
a changed baseline needs a fresh review even if its content fingerprint matches.
Context subprocesses inherit the pinned SHA through `DRESSCODE_BASE_COMMIT`.

Legacy run files remain untouched and cannot approve new baseline-keyed reviews.
Review again after upgrading; counters, retirements and trust remain intact.
After downgrading, run the legacy `dresscode reset` in each repository/branch
before relying on its gate, then review again.

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

## Review an exact commit

Use `diff REF` or `diff --base REF` for an exact commit, including unrelated
history. Supplying both selectors fails. Branches, remote refs, tags, commit IDs
and expressions such as `HEAD~2` work; empty/invalid refs, ambiguous abbreviated
IDs, ranges and non-commit objects fail. Git refname precedence applies; use
fully qualified names to disambiguate a branch and tag with the same name.

All seven review commands accept `--base REF`. Keep a resolved SHA across the
workflow so a moving ref cannot change the review:

```sh
dresscode diff HEAD~2 --numstat
BASE=$(git rev-parse HEAD~2)
dresscode list --base "$BASE" --json
dresscode answer shared-builder --base "$BASE" --yes --evidence "Reused the shared builder."
dresscode check --base "$BASE" --strict
dresscode report --base "$BASE"
dresscode reset --base "$BASE"
```

If a violation is accepted, record its violating verdict first, then use
`dresscode waive shared-builder --base "$BASE" --reason "<reason>"`.
The ordinary gate accepts current waivers; the strict gate rejects them.
Gate remedies include the resolved SHA.

Selection priority: explicit ref, inherited `DRESSCODE_BASE_COMMIT`, default
merge base. Explicit refs bypass the default target. Unqualified nested context
commands inherit the parent's SHA; explicit child refs are auxiliary evidence.
Inspection never selects a scope for later invocations. Equivalent baselines
share runs; different baselines isolate answers, history, context and waivers,
even with equal fingerprints. Reset clears only the selected run.
