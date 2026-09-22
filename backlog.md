# Backlog — deliberately deferred

- **Auto-decay of entries.** Rules should eventually fade: models improve, and a question answered clean for six months is probably burning tokens on every review. Deferred because the naive version is self-corrupting — a question the reviewer cannot detect looks identical to one the agent has mastered, so decay would delete exactly the rules that matter most. Needs an independent signal (human review outcomes, or the rule having been replaced by a deterministic gate) before it is safe.
- **CI reporting and trend stats.** Which questions still hit after N months?
- **Entry scoping by glob or tag,** so Python questions are not asked about a TypeScript diff. Deferred because the right axis is unknown: v0 answers an inapplicable question `n-a` with evidence, and those verdicts are the data that says whether paths, languages or something else is the real discriminator.
- **`ast-grep` rule stub emission on retire.** Only worth it once enough entries have actually turned out mechanizable; most will not.
- **`.gitattributes linguist-generated` as a size exclusion,** on top of the configured pathspec list.
- **Declared-versus-actual size ratio.** Rejected for v0 as gameable by inflating the declaration; revisit only if an honest declaration source appears.
