## Why

AI coding agents repeat the same mistakes. The rules that matter live as prose in `AGENTS.md`, which models weight inconsistently, while the rules that are mechanized (`ast-grep`, `ruff`, `pre-commit`) reliably police trivia. Nothing remembers what the agent actually gets wrong, and there is no conveyor belt from "prose rule that keeps losing" to "deterministic gate".

## What changes

DressCode stores a live list of questions about mistakes the agent commonly makes, hands them to a reviewer after implementation, records verdicts, and tracks each entry lifecycle.

```text
observed -> active question (prose, model-checked) --2nd hit--> mechanizable -> gate (ast-grep / ruff) -> retired
```

## v0 scope

- Per-repo state directory `.dresscode/` with entries carrying `id`, `question`, `scope`, `hit count`, `state` and timestamps.
- Command `dresscode list` returning the questions applicable to the current diff.
- Command `dresscode answer <id> --clean|--violated --evidence <text>` recording a verdict and bumping the hit count.
- Command `dresscode check` exiting non-zero when questions are unanswered or violations unfixed, suitable for `pre-commit`.
- Commands `dresscode add` and `dresscode retire`.
- Command `dresscode size` measuring the current diff against the merge base and exiting non-zero past a threshold.
- Every command offering `--json` so a hook, a gate and a subagent can all consume the output.

## Non-goals (v0)

- DressCode never spawns agents, never talks to a model, never edits code. Asking for the review is `AGENTS.md`'s job; backstopping it is `pre-commit`'s.
- No auto-decay of entries (see `backlog.md`).
- No team-shared rule packs, no CI service, no dashboard.

## Why a tool and not a markdown checklist

Entries carry counters and state transitions. A markdown list cannot count hits, cannot gate a commit, and cannot tell "the agent mastered this" from "the reviewer cannot detect this".
