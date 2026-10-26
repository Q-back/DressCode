# Task hand-over

Tests must pass before code changes can be declared complete. If tests fail or
cannot be run, report the blocker and leave the task incomplete.

Before declaring code changes complete, ask a fresh-context reviewer who has not
seen the implementation transcript to review the final cumulative changes. Do
not ask the implementer to substitute self-review for this independent pass.

For code changes, when `dresscode check` is available, require it to exit
successfully before hand-over. The gate covers the final cumulative diff;
intermediate commits do not need current verdicts. A passing gate records answers
but does not prove reviewer independence.

When only reviewing code, record answers and report findings. Do not change
reviewed code, add waivers or run `dresscode check`. Surface unanswered questions,
stale answers, context failures and command errors.
