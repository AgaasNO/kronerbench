# Contributing

Run `uv sync --dev`, `uv run pytest`, `uv run ruff check .` and `uv run mypy`.
Keep parser changes independent of model answers. Include a hand-calculated regression example.
Cases must be synthetic, carry a rationale, and use integers for minor units.
Never change a case to favor a hypothesis. Record disputed truth in `CASE_AUDIT.md`.
