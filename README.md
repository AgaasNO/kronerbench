# KronerBench

How often does an LLM commit the wrong money amount through a tool call?

KronerBench compares strict formatting, deterministic locale parsing, verbatim copying,
JSON numbers and selection from extracted candidates. Silent errors lead every result.

Implementation is in progress. No live benchmark findings have been published.

```sh
uv sync --dev
uv run kronerbench --help
uv run kronerbench selfcheck --skip-live
```

Exit codes: 0 success, 2 usage error, 3 credentials, 4 cost cap, 5 acceptance failures,
6 provider unavailable. Run `kronerbench <command> --help` for examples and cost notes.
