# Alignment

## Behavior changes

### 1. Review committed snapshots

- **[Review snapshot](specs/diff-scope/spec.md#requirement-committed-diff-definition)**: compare the selected baseline with the full resolved `HEAD` commit.
  - Was: compare the baseline with working content, including uncommitted work.
  - Commit implementation and tested fixes before each review.
- **[Approval freshness](specs/review-cycle/spec.md#requirement-verdicts-expire-with-the-reviewed-commit)**: answers apply to one exact reviewed commit within the selected baseline scope.
  - Was: approvals stayed valid when the reviewed files’ contents stayed the same, even if the commit changed.
  - [Waivers](specs/verdict-gate/spec.md#requirement-waivers) and [cached context](specs/context-commands/spec.md#requirement-scope-local-context-evidence) use the same commit boundary.
  - Message-only amendments, empty commits and excluded-only commits need fresh review.
- **[Review metadata](specs/diff-scope/spec.md#requirement-diff-command)**: expose full `head_commit` alongside `base_commit` and `run_key`.
  - Was: payloads identified reviewed content with `fingerprint`.
  - Remove `fingerprint` rather than retaining an alias.

### 2. Require clean review inputs

- **[Clean-tree boundary](specs/diff-scope/spec.md#requirement-clean-working-tree-for-review)** *(new)*: `diff`, `list`, `answer`, `waive` and `check` reject local changes with exit `2`.
  - Include staged, unstaged and non-ignored untracked paths throughout the repository.
  - Excluded paths and dirty submodules still block review.
  - Ignored files do not block review.
  - Configuration, `trust`, `reset` and reporting remain usable when dirty.
- **[Context command safety](specs/context-commands/spec.md#requirement-context-collection-stays-on-the-reviewed-commit)** *(new, agent decision)*: `list` can run commands that provide extra context for review questions. If a command leaves uncommitted changes or changes `HEAD`, `list` fails with an error saying that the repository changed, and saves none of the context collected during that run.
  - Recheck the checkout before saving any results from that invocation.
  - Keep previously saved context untouched on rejection.

### 3. Keep reporting available

- **[Report boundary](specs/verdict-gate/spec.md#requirement-human-report)**: report committed diff counts and recorded evidence even when the working tree is dirty.
  - Was: report used working-tree counts and fingerprint-based freshness.
  - Add only commit metadata and a warning that local edits are not covered.
  - Use JSON `working_tree_dirty` and overall status `failed` while dirty *(agent decision)*, as described in the [minimal report adaptation](design.md#5-give-report-the-smallest-necessary-adaptation).

### 4. Start fresh after upgrade

- **[Old approvals](specs/review-cycle/spec.md#requirement-legacy-run-safety)**: require new commit-bound answers instead of importing fingerprint-based verdicts, waivers or context.
  - Was: existing baseline-keyed fingerprint reviews could satisfy the gate.
  - Leave old review-state files in `$XDG_STATE_HOME/dresscode/runs/` untouched (default: `~/.local/state/dresscode/runs/`). Keep shared counters, retirements and trust.
  - Reset relevant scopes with the older CLI before relying on its gate after downgrade.
