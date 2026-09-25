# Decisions

- 2026-09-25: Load the existing local `.env` without overriding exported variables; exclude all environment files from git.
- 2026-09-25: Validate Jev through its endpoint listing and Decisions probe because `/api/v1/models` omits decision models; the live probe resolved to `typesafe/jev-1.13-20260917` and cost USD 0.000014238.
- 2026-09-25: The key has USD 50 remaining; include probes, audit and benchmark in the session spending ledger and use the lower of available credit and the requested cap.
- 2026-09-25: Use Python 3.12+, uv, Typer and Svelte with Observable Plot; preserve money as integer minor units or Decimal throughout validation.
- 2026-09-25: Keep offline acceptance distinct from live acceptance; missing evidence must fail selfcheck, never pass through a placeholder.
- 2026-09-25: The owner selected `AgaasNO/kronerbench` and requested a pull request; use a feature branch and leave merging to the owner.
- 2026-09-25: The repository does not yet exist; create an initial base commit before branching so GitHub can compare the implementation in a pull request.
