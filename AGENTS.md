# Task hand-over

Before declaring a code task complete, ask a fresh-context reviewer who has not
seen the implementation transcript to review the final cumulative changes. Do
not ask the implementer to substitute self-review for this independent pass.

When `dresscode check` is available, require it to exit successfully before
hand-over. The gate covers the final cumulative diff; intermediate commits do
not need current verdicts. A passing gate records answers but does not prove
reviewer independence.
