# KronerBench

**How often does an LLM put the wrong money amount in a ledger?**

[![CI](https://github.com/AgaasNO/kronerbench/actions/workflows/ci.yml/badge.svg)](https://github.com/AgaasNO/kronerbench/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
[![MIT](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![CC BY 4.0](https://img.shields.io/badge/data-CC_BY_4.0-blue)](LICENSE-DATA)

KronerBench compares strict amount formats with deterministic locale parsing,
verbatim copying, JSON numbers and selection from extracted candidates. Its main
metric is the **silent error rate**: wrong values actually committed through tools.
Rejected values are counted separately.

![Fixture report, not live benchmark evidence](docs/img/verdict-light-1440.png)

This is an implementation checkpoint. The screenshot uses deterministic fake models.
There are **no published live benchmark findings** yet. The live-price standard
estimate is USD 102.70, above the USD 75 spending cap. See the [estimate](results/standard-estimate.json)
and [remaining work](docs/STATUS.md).

## The problem in 30 seconds

`1.234,50`, `1,234.50` and `1 234,50` can all denote the same money amount.
A model can change a digit while converting the punctuation. A parser can also
accept a perfectly copied number and store the wrong value. Both mistakes can
look like successful tool calls.

KronerBench records the source, raw tool arguments, validator decisions and final
commitment. You can inspect an error all the way back to the document.

## Try it locally

```sh
uv sync --dev
uv run kronerbench parse 'kr 1.234,50-'
uv run kronerbench run --profile quick --dry-run --run-id fixture
uv run kronerbench report fixture --open
```

The parser returns `accepted: true`, `value: -123450`, `sign: -1`. Monetary values
are integer minor units, so `-123450` means minus 1,234.50 kroner.

A parser-only trap:

```sh
uv run kronerbench parse '1,234.50'                 # value: 123450
uv run kronerbench parse '1,234.50' --parser naive  # value: 123
```

The naive parser removes the decimal dot. This example is a deterministic parser
calculation, not a claim about model behavior.

For paid work, export `OPENROUTER_API_KEY` or put it in an untracked `.env`, then
run `uv run kronerbench doctor`, `uv run kronerbench estimate`, and review the
estimate before `uv run kronerbench run --profile quick --max-cost 1`.
The standard run remains blocked by the cap. Never commit a key.

## What's tested

| Suite | Cases | Main trap |
| --- | ---: | --- |
| Norwegian formats | 60 | `kr 12 500,--` |
| European formats | 70 | `49:-`, `€1,234.50`, `CHF 1'234.50` |
| Ambiguity | 30 | Unresolved totals and separators |
| Accounting notation | 25 | Parentheses, trailing minus and `CR` |
| Scale | 25 | `TNOK`, `MNOK`, `mrd.` |
| Words | 25 | Danish *halvfems*, Norwegian long-scale *billion* |
| Unicode | 25 | Invisible characters and unusual spaces |
| Long numbers | 40 | Repeated digits and internal zeros |
| Distractors | 30 | Identifiers beside the amount |
| Documents | 40 | Multi-field invoices and hotel folios |
| Percent | 45 | Fractions, percent, per mille and basis points |
| Dates | 30 | Day/month order |
| Derived, opt-in | 25 | Requested arithmetic |

The catalogue has 470 cases and 548 fields. It includes 180 authored traps and
290 generated cases. Synthetic identifiers are explicitly marked test data.
Every authored case includes its rationale.

## Conditions

| Condition | Tool value | Acceptance |
| --- | --- | --- |
| `strict` | String such as `1234,56` | Canonical regex |
| `strict_constrained` | Same string, schema pattern | Provider support required |
| `lenient` | Normally formatted amount | Deterministic safe parser |
| `verbatim` | Source substring | Safe parser and number-boundary provenance |
| `json_number` | Raw JSON number | Decimal decoding, whole minor units |
| `minor_units`, opt-in | Integer | Smallest currency unit |
| `select` | Candidate id | Deterministically extracted candidate |

Jev is a decision model. It only participates in selection and optional verification.
Its adapter preserves confidence, probabilities and the dated model snapshot.
The calibration and verifier reporting work is tracked in [implementation status](docs/STATUS.md).

## Inspect and reproduce

```sh
uv run kronerbench cases stats --json
uv run kronerbench cases show no-formats-0001
uv run kronerbench explain no-formats-0001 --run fixture
uv run kronerbench score fixture
uv run kronerbench export fixture --format parquet
uv run kronerbench selfcheck --skip-live
```

A run contains its case snapshot, manifest, complete request/response bodies in
SQLite, trial JSONL, field CSV/Parquet and summary JSON. Re-scoring costs nothing.
The report works from `file://` with no server or CDN.

`--help` on every command includes examples and cost notes. Exit codes are 0 for
success, 2 for usage errors, 3 for credentials, 4 for the cost cap, 5 for failed
acceptance checks, and 6 for provider unavailability.

## Develop and extend

Add a model to `config/models.yaml`, an authored case to `cases/handwritten/`,
or a format to `src/kronerbench/cases/styles.py`. Include a hand-calculated test
for each new format. A condition owns a prompt, schema and validator in
`src/kronerbench/conditions/core.py`. New suites also need a count and an explicit
sampling and scoring policy.

```sh
uv run pytest --cov=kronerbench.parsers --cov-branch --cov-report=json
uv run ruff check .
uv run mypy
pnpm --dir ui install
pnpm --dir ui build
pnpm --dir ui qa
```

The prebuilt UI ships with the Python source. Node is needed only to rebuild it.
Live contract tests require both `OPENROUTER_API_KEY` and `KRONERBENCH_LIVE=1`.

## Method and limitations

SER excludes API failures and counts flagged or rejected recoverable values as loud
failures. Currency errors have a separate column. Wilson intervals accompany rates;
paired comparisons use exact McNemar tests with Holm correction, and pooled
comparisons resample cases. Small samples cannot establish small differences near
a low base error rate.

Cases are synthetic and balanced across traps, so their error rate does not estimate
production prevalence. Provider routing, model updates, prompt wording and prices
can change results. No case audit or frozen analysis plan exists yet. Fixture output
must never be cited as evidence for a hypothesis.

## Prior work and licence

- Singh & Strouse, [Tokenization counts](https://arxiv.org/abs/2402.14903).
- Tam et al., [Let Me Speak Freely?](https://arxiv.org/abs/2408.02442), and the [dottxt response](https://blog.dottxt.ai/say-what-you-mean.html).
- Park et al., [Grammar-Aligned Decoding](https://arxiv.org/abs/2405.21047).
- [OpenRouter Jev tutorial](https://openrouter.ai/docs/guides/community/jev-tutorial).

Code is MIT. Cases and published results are CC BY 4.0. See [CITATION.cff](CITATION.cff).
