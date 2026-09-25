# Decisions

- 2026-09-25: Load the existing local `.env` without overriding exported variables; exclude all environment files from git.
- 2026-09-25: Validate Jev through its endpoint listing and Decisions probe because `/api/v1/models` omits decision models; the live probe resolved to `typesafe/jev-1.13-20260917` and cost USD 0.000014238.
- 2026-09-25: The key has USD 50 remaining; include probes, audit and benchmark in the session spending ledger and use the lower of available credit and the requested cap.
- 2026-09-25: Use Python 3.12+, uv, Typer and Svelte with Observable Plot; preserve money as integer minor units or Decimal throughout validation.
- 2026-09-25: Keep offline acceptance distinct from live acceptance; missing evidence must fail selfcheck, never pass through a placeholder.
- 2026-09-25: The owner selected `AgaasNO/kronerbench` and requested a pull request; use a feature branch and leave merging to the owner.
- 2026-09-25: The repository does not yet exist; create an initial base commit before branching so GitHub can compare the implementation in a pull request.
- 2026-09-25: Treat Norwegian informal `3/4-26` as day-first, as explicitly required by the examples; reject ambiguous `DD/MM/YYYY` slash forms.
- 2026-09-25: JSON monetary numbers with fractional minor units are loud rejections; no rounding policy is silently applied by the reference validator.
- 2026-09-25: The 372 reference vectors use explicit hand-calculated base values plus value-preserving currency wrappers; Hypothesis supplies separate random round-trip coverage.
- 2026-09-25: Exactly-two-decimal amount grammars cannot produce different accepted readings; assert this invariant rather than retain an unreachable ambiguity branch.
- 2026-09-25: Ship 180 authored traps and 290 explicitly labeled generated cases, totaling exactly 470 across the requested suites.
- 2026-09-25: Synthetic financial identifiers use all-zero fixtures and explicit test-document labels; do not claim that a realistic checksum proves an identifier belongs to nobody.
- 2026-09-25: Case sampling is balanced round-robin across suites after seeded shuffling, and excludes derived by default.
- 2026-09-25: Network failures with uncertain billing consume their conservative request ceiling in the cost guard instead of being counted as free.
- 2026-09-25: Preserve sub-cent JSON values as Decimal but reject their commitment; offline float analysis uses `round(float(value) * 100)` as the common storage implementation.
