"""Human report layout and terminal style contracts."""

import re
from io import StringIO
from typing import Any

import pytest
from rich.color import Color
from rich.console import Console
from rich.text import Text

from dresscode import report


@pytest.fixture
def summary() -> dict[str, Any]:
    return {
        "status": "failed",
        "diff": {"added": 12, "removed": 3, "base_commit": "a" * 40},
        "entries": [],
        "waivers": [],
    }


def output(
    monkeypatch: pytest.MonkeyPatch,
    summary: dict[str, Any],
    width: int,
    color: bool = False,
) -> tuple[str, Console]:
    stream = StringIO()
    console = Console(
        file=stream,
        width=width,
        force_terminal=color,
        no_color=not color,
        color_system="standard" if color else None,
    )
    monkeypatch.setattr(report, "Console", lambda **kwargs: console)
    report.render(summary)
    return stream.getvalue(), console


@pytest.mark.parametrize("width", [40, 80])
def test_report_blocks_preserve_fields_and_wrapping(
    monkeypatch: pytest.MonkeyPatch, summary: dict[str, Any], width: int
) -> None:
    evidence = "demo/very_long_directory/fruit_catalog.py:12 [Pear] before [Apple]."
    summary["entries"] = [
        {
            "id": "sorted-fruit-names-with-a-long-heading",
            "question": "Are [demo] fruit names sorted?\nCheck every name.",
            "state": "stale",
            "verdict": "no",
            "expected": "yes",
            "evidence": f"\x1b[31m{evidence}\x1b[0m\nSecond evidence line.",
            "reveal": "Keep [demo] names sorted.\nRetain all names.",
            "context_output": "[demo] catalog\nPear, Apple",
            "error": "Context command failed [exit 1].\nTry again.",
        },
        {
            "id": "unique-fruit-names",
            "question": "Are names unique?",
            "state": "unanswered",
            "verdict": None,
        },
    ]
    summary["waivers"] = [
        {
            "id": "sorted-fruit-names-with-a-long-heading",
            "state": "stale",
            "reason": "Accepted [demo] order.\nRevisit later.",
        }
    ]
    rendered, _ = output(monkeypatch, summary, width)
    assert "\x1b[" not in rendered
    assert all(len(line) <= width for line in rendered.splitlines())
    rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
    first, second = re.split(r"Rule:\s+", rendered)[1:]
    assert "".join(first.split()).startswith("sorted-fruit-names-with-a-long-heading")
    assert "[stale]" in first
    assert "Verdict: no (expected yes)" in first
    assert "Question: Are [demo]" in first
    assert "\n\nEvidence:\n  " in first
    assert "\n  Second evidence line.\n" in first
    assert "\n  Pear, Apple\n" in first
    assert "Context error:" in first and "Try again." in first
    assert "Reveal: Keep [demo]" in first
    # Remove only layout whitespace, retaining every character of long values.
    compact = "".join(rendered.split())
    for value in (evidence, summary["diff"]["base_commit"], "Retain all names."):
        assert "".join(value.split()) in compact
    assert second.startswith("unique-fruit-names [unanswered]")
    assert "Verdict: unanswered" in second
    assert "Evidence:" not in second and "Reveal:" not in second
    assert "Expected:" not in rendered
    assert rendered.count("-" * width) == 2
    assert "\n\n" + "-" * width in rendered
    assert "\n\nWaivers\n" in second
    assert "[stale]: Accepted [demo] order." in " ".join(second.split())
    assert "Revisit later." in second


@pytest.mark.parametrize(
    "state,verdict,expected,color,annotation",
    [
        ("passed", "yes", "yes", "green", ""),
        ("passed", "no", "no", "green", ""),
        ("passed", "n-a", "yes", "green", ""),
        ("violated", "yes", "no", "red", " (expected no)"),
        ("violated", "no", "yes", "red", " (expected yes)"),
        ("stale", "no", "yes", "yellow", " (expected yes)"),
        ("waived", "yes", "no", "yellow", " (expected no)"),
        ("context_failed", None, None, "red", ""),
        ("context_untrusted", None, None, "yellow", ""),
        ("unanswered", None, None, "yellow", ""),
    ],
)
def test_report_styles_follow_state_and_field_roles(
    monkeypatch: pytest.MonkeyPatch,
    summary: dict[str, Any],
    state: str,
    verdict: str | None,
    expected: str | None,
    color: str,
    annotation: str,
) -> None:
    entry = {"id": "fruit", "question": "Sorted?", "state": state, "verdict": verdict}
    if verdict is not None:
        entry.update(
            expected=expected, evidence="Reviewed [demo].", reveal="Sort names."
        )
    entry["context_output"] = "Recorded [catalog]."
    summary["entries"] = [entry]
    rendered, console = output(monkeypatch, summary, 80, color=True)
    text = Text.from_ansi(rendered)

    def style(value: str):
        return text.get_style_at_offset(console, text.plain.index(value))

    def color_number(value: str):
        foreground = style(value).color
        assert foreground is not None
        return foreground.number

    assert style("Rule: fruit").bold
    assert color_number("Rule: fruit") == Color.parse("cyan").number
    assert color_number(f"[{state}]") == Color.parse(color).number
    verdict_text = f"Verdict: {verdict or 'unanswered'}{annotation}"
    assert verdict_text in text.plain
    assert style("Verdict:").bold
    assert color_number("Verdict:") == Color.parse(color).number
    assert style("Question:").dim and style("Sorted?").dim
    assert not style("Recorded [catalog].").dim
    assert style("Context:").bold
    if verdict is not None:
        assert style("Evidence:").bold
        assert not style("Reviewed [demo].").dim
        assert style("Reveal:").dim and style("Sort names.").dim
    else:
        assert "expected" not in text.plain and "Reveal:" not in text.plain
    assert "Expected:" not in text.plain


@pytest.mark.parametrize(
    "status,color",
    [("failed", "red"), ("passed", "green"), ("passed-with-waivers", "yellow")],
)
def test_overall_status_style(
    monkeypatch: pytest.MonkeyPatch, summary: dict[str, Any], status: str, color: str
) -> None:
    summary["status"] = status
    rendered, console = output(monkeypatch, summary, 80, color=True)
    text = Text.from_ansi(rendered)
    foreground = text.get_style_at_offset(console, 0).color
    assert foreground is not None and foreground.number == Color.parse(color).number
