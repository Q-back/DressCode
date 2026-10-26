# Proposal

## Why

`dresscode report` gives rule names, questions, verdicts, evidence and reveals almost the same visual weight. Long entries blend together, making the rule, verdict and evidence hard to find even though this command is intended for people.

## What Changes

- Give every rule a separate block with an explicit rule heading, a separator and space between blocks.
- Make rule headings, verdicts and evidence labels stand out with terminal styling.
- Keep the verdict compact: show the recorded answer, adding `(expected yes)` or `(expected no)` only for a conflicting yes/no answer. Keep the current state beside the rule heading.
- Keep Question and Reveal visible by default, but slightly muted relative to evidence. Do not introduce a verbosity flag.
- Preserve readable grouping without color, including redirected output.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `verdict-gate`: Strengthen the Human report requirement with per-rule separation, field hierarchy, compact verdicts and semantic terminal styling.

## Impact

- Update rendering in `dresscode/report.py`, using the existing Rich dependency.
- Extend report coverage in `dresscode/test_gate_cli.py` and end-to-end workflow tests, and update the report description in `README.md`.
- Leave JSON payloads, stored review data, sealed-question behavior and gate decisions unchanged. This change affects only the human report, not other CLI commands.
