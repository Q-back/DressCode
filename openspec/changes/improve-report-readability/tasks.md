# Tasks

## 1. Commit group: Make the human report easy to scan

Land the renderer, its tests and the README update together. Keep any later review fixes in separate commits and re-review them before completing this group.

- [x] 1.1 Add failing report regressions for the spec delta: separated multi-rule blocks, compact matching/conflicting/`n-a` verdicts, unanswered sealed fields, state-aware styles, normal-contrast evidence, muted but visible Question and Reveal, context errors/output and stale waivers. Exercise 40- and 80-column output, multiline and bracketed text, and ANSI-free redirected output; run the focused tests and confirm the new assertions fail against the old renderer.
- [x] 1.2 Update `dresscode/report.py` using the existing Rich dependency and the design's stacked layout. Leave summary data and JSON serialization unchanged; verify all focused report tests pass, including semantic style assertions and no-loss wrapping.
- [x] 1.3 Add a real CLI multi-rule workflow regression with long evidence, both expected-answer values and stale recorded answers. Verify field grouping, retained Question/Reveal/context, full baseline IDs, the separate waivers section and unchanged JSON through actual CLI invocations; run the workflow tests successfully.
- [x] 1.4 Update the report section of `README.md` to explain the hierarchy, inline expectations and color-free grouping. Verify the description against a rendered example and confirm it introduces no verbosity flag or JSON change.
- [x] 1.5 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check` and `openspec validate improve-report-readability --strict`. Inspect the cumulative diff and count added lines at this green boundary, then commit the implementation, tests and documentation together.
- [x] 1.6 Load `agent-code-review` and obtain a fresh-context, read-only review of the cumulative change, including unchanged JSON and gate consumers, sealed fields and any removed human output. Resolve in-scope findings in separate commits, rerun required checks and obtain re-review; verify there are no unresolved blocking findings.
- [x] 1.7 Obtain current DressCode answers for the final cumulative diff and require `dresscode check` to exit successfully before hand-over. Verify the text report visually at ordinary and narrow widths, with and without color, against the agreed hierarchy.
