# Design

## Context

See [proposal.md](proposal.md) for the problem and [the spec delta](specs/verdict-gate/spec.md) for the behavior contract.

`dresscode/report.py` already separates `summarize()` from `render()`. The summary carries each entry's ID, question, current state and recorded verdict; answered entries also carry the expectation, evidence and reveal. Rendering uses Rich, but only the overall status receives an application-defined style. Existing tests protect sealed fields, recorded context, stale waivers and ANSI-free redirected output.

## Goals / Non-Goals

**Goals:** Make the hierarchy work at ordinary and narrow terminal widths without changing review data. Keep presentation decisions inside the report renderer.

**Non-Goals:** Rework other commands, change review ordering, introduce filtering or verbosity flags, or add a rendering dependency.

## Decisions

### Use stacked blocks rather than tables or enclosing panels

Render each entry as a full-width ASCII separator and a `Rule:` heading, followed by labeled fields with blank space between the main groups. A heading may share its separator line when it fits; long headings must wrap rather than disappear. Use the available console width rather than a fixed border width.

Fictional fruit-catalog example, before terminal styling:

```text
--- Rule: sorted-fruit-names [stale] ------------------

Question: Are the demo fruit names sorted alphabetically?

Verdict: no (expected yes)

Evidence:
  demo/fruit_catalog.py:12 lists "Pear" before "Apple".
  The remaining names are in alphabetical order.

Reveal: Keep demo fruit names in alphabetical order.


--- Rule: unique-fruit-names [stale] ------------------
```

Keep wrapped continuations under their field and preserve multiline content. Recorded context output and labeled context errors stay inside the corresponding block. Keep waivers in their existing separate section, with comparable spacing.

A table would squeeze long evidence into a column. Enclosing panels would consume width on both sides and add more decoration than separation requires.

### Make styles explicit and secondary text mildly dim

Compose Rich `Text` values rather than interpolating user text into Rich markup. Use bold cyan for rule headings, bold for field labels, and normal contrast for evidence and recorded context. Apply Rich's dim attribute to Question and Reveal, including their labels; do not remove or collapse either field.

Use the entry's current state for state styling and the default verdict styling:

- `passed`: green, including a satisfied `no` or `n-a` answer.
- `violated` and `context_failed`: red.
- `stale`, `unanswered`, `waived` and `context_untrusted`: yellow.

A stale yes/no verdict that matches its expected answer is green. Its `[stale]` state remains yellow. Stale conflicting and `n-a` verdicts retain yellow styling.

Keep the state visible as text beside the rule ID. Use red, green and yellow respectively for the overall `failed`, `passed` and `passed-with-waivers` statuses. Color reinforces labels; it never replaces them. Avoid dimming the entire entry or its evidence.

### Keep the expectation inline and conditional

Build the verdict text from the recorded verdict and expectation, independently of freshness. Append `(expected yes)` or `(expected no)` only for a conflicting yes/no pair. Matching answers and `n-a` need no annotation. A stale conflicting answer still retains its annotation, while its state styling warns that it is not current. With no recorded verdict, show `Verdict: unanswered` without accessing sealed fields or fabricating evidence.

A separate Expected field duplicates a label on every rule and weakens the scan path. Omitting the expectation on conflicts would make the failure harder to interpret.

### Preserve the structured boundary and test actual output

Leave `summarize()`, the JSON branch in `dresscode/cli.py`, gate decisions and stored state unchanged. Keep non-TTY color suppression and the existing embedded-ANSI stripping behavior. Preserve literal field contents, including bracketed text, without treating them as markup or truncating them for layout.

Add focused renderer tests at controlled widths, with terminal styling enabled and disabled. Check style roles as well as visible text, so a single colored overall status cannot satisfy the regression. Add a real CLI workflow with multiple rules and long evidence to exercise grouping, state transitions and redirected output without mocking review data. Retain the existing JSON and sealed-field regressions.

## Risks / Trade-offs

- More vertical space per rule -> Keep the verdict on one logical line and avoid redundant expectation/state labels. The added space is deliberate separation.
- Muted text can become hard to read -> Dim only Question and Reveal; keep evidence, verdicts and warnings at normal contrast or stronger.
- A green stale verdict could look like a current pass -> Keep `[stale]` yellow and visible in the heading; gate decisions still reject stale answers.
- Narrow terminals can split headings and long paths -> Allow wrapping and test 40- and 80-column output, including full baseline IDs and multiline evidence.
- Exact ANSI snapshots can be brittle -> Assert semantic styling and grouping rather than incidental escape-code ordering or separator length.

## Migration Plan

No data migration is needed. Ship as a renderer, tests and README update in one commit group. Rollback restores the previous renderer without changing stored reviews or JSON consumers.
