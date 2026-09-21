# Backlog — deliberately deferred

- **Auto-decay of entries.** Rules should eventually fade: models improve, and a question answered clean for six months is probably burning tokens on every review. Deferred because the naive version is self-corrupting — a question the reviewer cannot detect looks identical to one the agent has mastered, so decay would delete exactly the rules that matter most. Needs an independent signal (human review outcomes, or graduation to a gate) before it is safe.
- **Team-shared rule packs and importable presets.** Let a team author a pack once and reuse it across repos.
- **CI reporting and trend stats.** Which questions still hit after N months?
- **Auto-generating an ast-grep rule stub when an entry reaches the mechanizable state.**
- **Language-specific starter packs.**
