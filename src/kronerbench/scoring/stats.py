"""Pre-specified intervals and paired tests."""

import math
from collections import defaultdict
from typing import Any

import numpy as np
from scipy.stats import binomtest


def wilson(k: int, n: int) -> list[float | None]:
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    middle = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0, middle - half), min(1, middle + half)]


def paired(a: list[int], b: list[int]) -> dict[str, Any]:
    if not a:
        return {"n": 0, "difference": None, "ci": [None, None], "p": None}
    n = len(a)
    positive = sum(x == 1 and y == 0 for x, y in zip(a, b, strict=True))
    negative = sum(x == 0 and y == 1 for x, y in zip(a, b, strict=True))
    delta = (positive - negative) / n
    # Paired score interval (Newcombe): Wilson intervals for discordant proportions.
    pa, pb = wilson(positive, n), wilson(negative, n)
    assert all(v is not None for v in pa + pb)
    lo = delta - math.sqrt((positive / n - float(pa[0])) ** 2 + (float(pb[1]) - negative / n) ** 2)  # type: ignore[arg-type]
    hi = delta + math.sqrt((float(pa[1]) - positive / n) ** 2 + (negative / n - float(pb[0])) ** 2)  # type: ignore[arg-type]
    p = float(binomtest(positive, positive + negative, 0.5).pvalue) if positive + negative else 1.0
    return {
        "n": n,
        "difference": delta,
        "ci": [max(-1, lo), min(1, hi)],
        "p": p,
        "strict_only": positive,
        "lenient_only": negative,
    }


def holm(tests: list[dict[str, Any]]) -> None:
    valid = sorted([t for t in tests if t["p"] is not None], key=lambda t: t["p"])
    last = 0.0
    for i, test in enumerate(valid):
        last = max(last, min(1.0, test["p"] * (len(valid) - i)))
        test["p_adjusted"] = last


def cluster_bootstrap(
    pairs: list[tuple[str, int, int]], seed: int = 42, resamples: int = 2000
) -> dict[str, Any]:
    groups: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for case, a, b in pairs:
        groups[case].append((a, b))
    if not groups:
        return {"difference": None, "ci": [None, None], "cases": 0}
    sums = np.array([sum(a - b for a, b in group) for group in groups.values()], dtype=float)
    counts = np.array([len(group) for group in groups.values()], dtype=float)
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(groups), size=(resamples, len(groups)))
    values = sums[samples].sum(axis=1) / counts[samples].sum(axis=1)
    return {
        "difference": float(sums.sum() / counts.sum()),
        "ci": [float(v) for v in np.quantile(values, [0.025, 0.975])],
        "cases": len(groups),
        "resamples": resamples,
    }
