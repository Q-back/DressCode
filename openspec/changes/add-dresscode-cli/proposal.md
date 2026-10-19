## Why

AI coding agents repeat the same mistakes. The rules that matter live as prose in `AGENTS.md`, which fades from attention over a long implementation and which models weight inconsistently, while the rules that are mechanized (`ast-grep`, `ruff`, `pre-commit`) reliably police trivia. Nothing checks, at hand-over time, that the taste a given production repo demands was actually honoured — and nothing remembers what the agent gets wrong.

## What changes

DressCode stores a list of boolean questions about mistakes the agent commonly makes, hands them to a fresh-context reviewer after implementation with the wanted answer sealed, records verdicts against the current diff, and refuses to go green until every question is answered as expected or the violation is documented.

```text
implement ──> dresscode list      questions only, expectations sealed
              dresscode answer    verdict + evidence  -> reveal printed back
              dresscode waive     violation ships, with a reason on the record
              dresscode check     the gate: all green, or exactly what to fix
              dresscode report    human read-out at the end of the task
```

## v0 scope

- Global run state keyed by repo and branch, in `$XDG_STATE_HOME/dresscode/`, with every verdict pinned to a fingerprint of the diff it was given.
- Three-layer config: `~/.config/dresscode/repos/<repo_id>.toml`, repo-local `.dresscode/`, `~/.config/dresscode/config.toml`, merged by entry `id`.
- Entries carrying `id`, `question`, sealed `expects` and `reveal`, optional `context` command, counters and timestamps.
- `dresscode list` — the applicable questions plus their context command output, never the expectation.
- `dresscode answer <id> --yes|--no|--n-a --evidence <text>` — records the verdict, then prints the reveal.
- `dresscode waive <id> --reason <text>` — lets a violation ship, on the record.
- `dresscode check [--strict]` — the gate before the agent declares the task done, covering the final cumulative diff rather than intermediate commits: exit `0` green or waived, `1` action needed with the fixing command named per entry, `2` usage error. `--strict` fails on waivers.
- `dresscode report` — colorful human summary of why the task is believed done, showing verdicts, evidence and waivers.
- `dresscode add`, `dresscode retire <id> [--reason]`, `dresscode reset`, `dresscode trust`.
- `dresscode diff [--numstat]` — the diff definition as a command, so entries can use it as context; merge base to working tree, untracked included, configured exclusions applied.
- Every command offering `--json` so a harness, a hand-over gate and a subagent can all consume the output.
- Python and `uv`, installable with `uv tool install .`.

## Non-goals (v0)

- DressCode never spawns agents, never talks to a model, never edits code. Requiring a fresh-context reviewer and running `dresscode check` before hand-over are `AGENTS.md`'s or the harness's job. DressCode does not install or require Git hooks; intermediate commits remain unrestricted by DressCode.
- No reviewer-independence checks (see `backlog.md`). A passing gate is not proof of independent review.
- No lifecycle automation: entries do not graduate to `ast-grep` on their own and do not decay (see `backlog.md`).
- No entry scoping by glob or tag; an inapplicable question is answered `n-a`.
- No seeded rule list, no team-shared rule packs, no CI service, no dashboard.

## Why a tool and not a markdown checklist

A markdown list cannot seal the wanted answer from the reviewer, cannot bind a verdict to the diff it was given, cannot tell a documented violation from an undocumented one, and cannot gate hand-over of the final result.
