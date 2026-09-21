## Context

This comes out of a design session on making agent code quality enforceable rather than advisory. Two companion pieces: the `nanny` pi extension (session context and cost observer, separate repo) and the mechanized gates already present in target repos (`ast-grep` rule directories, `ruff`, `pre-commit`).

## Decisions taken

1. **Pure CLI, no orchestration.** Single responsibility: own the entry state and answer questions about the current diff. Deciding to run a review belongs to the harness.
2. **Questions, not rules.** Entries read as questions, for example "Did you reuse an existing test factory instead of hand-rolling a mock?". A question forces a lookup; a rule statement invites agreement.
3. **The answerer must be a fresh-context reviewer that never saw the implementation transcript, never the implementer itself.** DressCode cannot enforce this; it is a contract for callers, enforced by the `nanny` and `pre-commit` wiring.
4. **Graduation is the exit, not decay.** An entry with two or more hits is flagged `mechanizable` and should become an `ast-grep` or `ruff` rule; once the rule exists the entry is retired.
5. **Machine-readable first.** Every command supports `--json`.
6. **The size and slice gate lives here, as `dresscode size`.** It is the same kind of thing: a per-diff check that must pass before work is handed over. Without it a human ends up reviewing 900 lines of evidence.

## Open questions

1. **Implementation language and runtime** — TypeScript (matches pi, shares types with the `nanny` extension), Python (matches most target repos and `pre-commit`), or Go (single binary, no runtime)?
2. **Where does state live, and is it committed?** Repo-local and committed makes rules reviewable in merge requests; gitignored keeps it personal; a global store with per-repo overrides is a third option.
3. **How is "the current diff" defined** — merge base against `origin/HEAD`, staged changes only, or the working tree? This decides whether `check` can have identical semantics in `pre-commit` and in CI.
4. **How do answers arrive** — one answer call per entry, or a single JSON report on stdin from the reviewing subagent? One round trip versus resumability.
5. **How does an entry scope to paths or languages**, so Python questions are not asked about a TypeScript diff — globs, tags, or something else?
6. **On graduation, does DressCode emit an `ast-grep` rule stub**, or only flag the entry as `mechanizable` and leave authoring to the human?
7. **Size gate semantics**: absolute authored-line threshold, or declared-versus-actual ratio? What is excluded (generated code, lockfiles, vendored trees, snapshots, fixtures), and where does the declaration live — the OpenSpec proposal?
8. **What stops DressCode becoming a second prose rulebook alongside `AGENTS.md`?** Candidate rule: a question may only exist here once it has been observed at least once in real output.
9. **Seeding**: bootstrap from a list of known recurring sins, or start empty and let the list earn its entries?
10. **Failure ergonomics**: what exactly does `check` print so the agent can act on it without a human translating?
