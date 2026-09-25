# Budget pilot analysis plan

This plan is frozen before the first paid benchmark run. The budget pilot is a reduced
experiment requested by the owner, with a USD 5 ceiling including the smoke test.
It does not replace the complete standard study or its acceptance checklist.

## Selection and spending

- Use the `budget` profile with seed 42, one repeat, and 240 cases sampled evenly across
  the 12 default suites. Derived arithmetic is excluded.
- Case-set SHA-256: `707a40c0e46654fdedf92a49034b319267552da0a56423ad4bf1de5b02e834bd`.
- Models: GPT-5.6 Luna, DeepSeek V4.1 Flash, GLM 5.3 Flash, Tencent Hy3 and Jev 1.13.
- The four LLMs run strict, lenient, JSON number and select. Jev runs select only.
  Selection skips words and cases exceeding 20 candidates, with explicit reasons.
- Verbatim, constrained strict, minor units, the verifier, Norwegian prompts and
  frontier models are outside this pilot. Do not infer their behavior from it.
- Smoke-test the same models on no-formats-0001, which is absent from the pilot sample.
  Reserve at most USD 0.10 for the smoke test; deduct its actual conservative cost
  from the USD 5 budget before starting the pilot.
- Current planning estimate is USD 3.3393792 at the maximum advertised endpoint rates.
  Prices and request sizes can change. The cost guard reserves each request ceiling
  before sending it and saves unsettled charges for conservative recovery.
- Stop rather than raise the cap or launch a second paid experiment automatically.

## Primary comparison

The primary outcome is the share of scored money fields with a wrong committed value.
Flags and rejected values are loud outcomes. API failures are excluded and disclosed.
Currency is scored separately. Rate and date suites appear in secondary tables and
are excluded from the primary paired money comparison.

Compare strict and lenient on matching model, case, field and repeat. Report the
strict-minus-lenient SER difference per model, exact McNemar p-values with Holm
correction across all condition comparisons for that model, and score intervals
constructed from Wilson intervals for discordant proportions. The pooled difference
uses 2,000 bootstrap resamples of whole cases, seed 42, retaining the models and fields
within each case. Intervals crossing zero are inconclusive. Degenerate bootstrap
intervals when no differences are observed do not establish equivalence.

Report SER, accuracy and loud rate with Wilson 95% intervals for every model,
condition and suite. Also report first-attempt compliance, retry digit drift,
corruption and rescue, input/output/reasoning tokens, latency and cost.

Offline safe-eu, safe-no and naive comparisons use identical lenient first-attempt
strings. Float conversion is evaluated on raw Decimal-preserved JSON numbers.
These require no additional paid calls.

## Jev selection

Split by SHA-256 of the JSON-encoded case id: the first eight hexadecimal digits
modulo 100 below 30 are calibration; the rest are evaluation. All fields in one
case remain together. Record every choice, probability, confidence and ambiguity score.

Consider confidence thresholds 0.00 through 1.00 in increments of 0.01, fixing
ambiguity below 0.5. Choose the smallest threshold with at least 10 calibration
commitments and an observed calibration SER no greater than 1%. If none qualifies,
use 1.01 and abstain. This empirical rule is not a statistical guarantee of 1% risk.

Apply that threshold to field scoring; headline Jev cells use evaluation cases only.
Preserve raw provisional decisions in the transcripts. Report held-out risk/coverage
curves and reliability bins of width 0.1. Confidence measures concentration, so
its expected calibration error is descriptive rather than proof of correctness.

## Scope and limitations

This pilot can estimate the direction of the strict-versus-lenient effect for these
four economical LLMs. Other hypotheses remain secondary or untested; the number-length
interaction is exploratory. No claim about frontier models or all LLMs is warranted.

The synthetic cases have not completed the two-strong-model live audit. The audit
is deferred to preserve the owner's spending limit. Findings are provisional;
report possible ground-truth or instruction problems rather than editing the truth
after seeing outcomes. A few hundred fields have low power for small SER differences.
Any analysis added after this commit must be labeled exploratory.
