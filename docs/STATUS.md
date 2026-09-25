# Implementation status

The offline development checklist passes. The published benchmark checklist does not.

Completed and checked:

- CLI command tree and Examples help, 372 parser vectors, property tests and 100% parser branch coverage.
- 470 schema-valid synthetic cases, with 180 authored traps and deterministic generation.
- Fake-model tool loops, per-field retries, immutable commitments, response cache and re-scoring.
- Structured manifests, transcripts, CSV/Parquet field tables, offline parser analyses and paired statistics.
- Eleven report pages, tested in Chromium in light and dark mode at 1440 and 390 pixels.

Live work stopped at the spending roadblock. `results/standard-estimate.json` projects USD 102.70,
above the authorized USD 75 cap. The local key had USD 50 remaining at preflight.
The single Jev probe cost USD 0.000014238. No quick, audit or standard run has been launched.

Remaining before publication:

- Complete M6 live contracts, the quick run and two-model audit. Resolve or document ground-truth disputes.
- Freeze and commit `ANALYSIS_PLAN.md` before any standard run.
- Apply Jev calibration thresholds to headline evaluation rows, and implement the verifier's risk/coverage analysis.
- Finish falsifiable decision rules for H2–H8. Current report labels these inconclusive; H1's length interaction is exploratory.
- Replace retry transition bars with the specified alluvial and add the Pareto frontier.
- Harden crash/cancellation cost accounting, resume identity and unsupported-parameter fairness across conditions.
- Complete installed-wheel resource lookup; this revision is supported from a source checkout.
- Run the complete standard profile after the owner raises the cap and supplies enough credit.
- Replace fixture screenshots and README examples with the published run's numbers, validate their provenance,
  then deploy Pages and attach the complete run to release v0.1.0.

The PR is an implementation checkpoint. It does not establish any research finding.
