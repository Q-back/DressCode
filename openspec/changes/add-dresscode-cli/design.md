## Context

This comes out of a design session on making agent code quality enforceable rather than advisory. It sits alongside the mechanized gates already present in target repos (`ast-grep` rule directories, `ruff`, `pre-commit`), and covers the part they cannot reach: the taste and flavour a large production repo demands, which no pattern matcher expresses.

## Decisions taken

### The question

1. **Pure CLI, no orchestration.** Single responsibility: own the review state and serve questions about the current diff. Deciding to run a review belongs to the harness.
2. **Questions, not rules.** Entries read as questions, for example "Did you reuse an existing test factory instead of hand-rolling a mock?". A question forces a lookup; a rule statement invites agreement.
3. **Every question is answerable `yes` / `no`, and the expected answer is sealed.** An entry carries `question`, a hidden `expects` (`true` or `false`), and a hidden `reveal` explaining why. `dresscode list` emits neither hidden field; `dresscode answer` prints the reveal in its response, after the verdict is recorded. A reviewer that knows the wanted answer supplies it. Two consequences: polarity is mixed deliberately, so the list never teaches "say yes"; and a determined reviewer can still read the store off disk — this is an honesty rail, not a sandbox.
4. **`n-a` is a third verdict.** It never fails the gate, it is recorded with evidence, and it is the deliberate stand-in for entry scoping (see Deferred).
5. **An entry may attach a read-only context command** whose stdout is handed to the reviewer alongside the question. The size gate is exactly this and nothing more: question "Are the added lines in this change under 400?" plus `dresscode diff --numstat`. Commands from the repo-local layer execute code that arrived with a clone, so they run only after a one-time `dresscode trust`, direnv-style; global-layer commands always run. A failing command marks the answer `context_failed` rather than letting it pass quietly, and the recorded stdout goes into the run state so `report` shows what the reviewer actually saw.

### The reviewer

6. **Fresh-context review is a workflow requirement, not a CLI check.** `AGENTS.md` or the harness must request a reviewer that never saw the implementation transcript, rather than asking the implementer to grade itself. The CLI gates recorded answers, not reviewer independence (see Deferred).

### The verdict

7. **A violation may ship, as a recorded waiver.** `dresscode waive <id> --reason` makes `check` exit zero with status `passed-with-waivers`; `check --strict` (CI) still fails. Added lines at 703 against a 400 threshold with a reason the change cannot be sliced is a legitimate pass. Waivers are pinned to the same diff fingerprint as the answer and die with the run; a permanent exemption is an edit to the entry, not a waiver.
8. **Entries accumulate evidence; they do not graduate.** Not every rule reduces to `ast-grep` — that is why this tool exists. Counters (`asked`, `violated`, `last_violated`) are input for a human deciding what to keep, not a state machine. Mechanization is one optional reason passed to `dresscode retire`.
9. **Two surfaces, no third.** `check` is the machine gate before task hand-over: exit `0` all green or waived, `1` action needed, `2` usage or config error, `--json` throughout. `report` is the human end-of-task read: colorful, small, waivers in their own section. On failure `check` names each entry, its state (`unanswered`, `stale`, `context_failed`, `violated`), and the exact command that clears it.

### State and scope

10. **Keep one review run per repo and branch. Answers only cover the changes reviewed.**

    Two values do different jobs:

    - **Run key: which review run to use.** Join the repo identity and branch name with `:`: `run_key = repo_id + ":" + branch`. For example, if `repo_id` is `acme/dresscode` and the branch is `feature/add-cli`, the key is `acme/dresscode:feature/add-cli`. How `repo_id` is chosen is described in decision 11. Without a checked-out branch (detached HEAD), use `detached-<sha>` in place of the branch name.
    - **Diff fingerprint: whether the reviewed changes are still the same.** The fingerprint is a SHA-256 hash: a value calculated from the reviewed diff's contents. Save it with each answer. It covers the changes included in the review, not excluded files. Before allowing hand-over, `dresscode check` compares the saved fingerprint with the current one. If they differ, the answer is `stale` and the reviewer must answer again.

    ```text
    answer a question → save the answer and the current diff fingerprint
    edit reviewed code → the diff fingerprint changes
    dresscode check → stale answer; a new answer is required
    ```

    This prevents an answer from approving code added after the review. Staging or committing the same changes does not make an answer stale, as long as the merge base stays the same.

    The run belongs to the repo and branch, not the agent session or a working directory. That lets it survive session restarts and keeps different branches separate. Git normally prevents two worktrees from using the same branch, so they get separate runs too.
11. **State is a global store; config is three layers.** Run state lives in `$XDG_STATE_HOME/dresscode/runs/`, never in the repo — it is churn no reviewer wants in a merge request. Config resolves highest-first: `~/.config/dresscode/repos/<repo_id>.toml` (private, per-repo, wins), then repo-local `.dresscode/` (team rules, reviewable in merge requests), then `~/.config/dresscode/config.toml` (yours everywhere). Entries merge by `id`; a higher layer overrides fields or sets `enabled = false` to kill a lower entry. `repo_id` is the normalized origin URL, falling back to the realpath of the main worktree.
12. **The current diff is merge base to working tree, untracked files included.** `base = config.base_ref ?? origin/HEAD ?? default branch`, then `git diff --merge-base $base` plus `git ls-files --others --exclude-standard` counted as additions. The reviewer must see the final cumulative change across all intermediate commits, including uncommitted work. In a clean checkout, as in CI, this reduces to the committed branch diff against the merge base. Staged-only would let an agent hide a whole new module from the review.
13. **Size counts added lines, absolutely.** Deletions are excluded, because counting them punishes deleting code, and there is no declared-versus-actual ratio: it needs a declaration to exist and is gamed by inflating it. The threshold is not a config key — it lives in the question text ("under 400?"), which is already per-repo because the question is; `dresscode diff` only reports counts. What is configured is `diff.exclude`, a pathspec list defaulting to lockfiles, `vendor/`, snapshots, cassettes and fixtures.

### Delivery

14. **Python and `uv`, shaped like `~/Work/metronome`.** `uv tool install .`, `[project.scripts] dresscode = "dresscode.cli:main"`, `typer` and `rich`, `ruff` + `ty` + `pytest` with `test_*.py` colocated in the package, Python pinned by `.python-version`.
15. **The list starts empty.** Nothing is seeded; entries are added when a mistake is actually observed.
16. **Gate hand-over, not intermediate commits.** `AGENTS.md` or the harness requires `dresscode check` before the agent declares the task done, not before each commit. The agent may make any number of intermediate commits without current verdicts; DressCode does not install or require Git hooks. At hand-over, `check` fails until every question about the final cumulative diff is answered as expected or the violation is documented, and `report` shows a human why the task is believed done. This enforcement timing, not different content, is what separates DressCode from `AGENTS.md` prose; overlap is fine, and "must have been observed once" is authoring advice rather than a constraint.

## Deferred

Recorded in `backlog.md`: reviewer-independence checks, entry scoping by glob or tag (`n-a` verdicts collect the evidence for what it should be), `ast-grep` stub emission on retire, `.gitattributes linguist-generated` as a size exclusion, auto-decay of entries.
