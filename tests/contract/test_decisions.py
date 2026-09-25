import os

import pytest

from kronerbench.providers.openrouter import ProviderError, doctor
from kronerbench.providers.openrouter_decisions import validate_response


def test_decisions_contract_rejects_schema_drift():
    good = {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            "pick": {"choice": "c1", "confidence": 0.9, "probabilities": {"c1": 0.9, "none": 0.1}},
            "ambiguous": {"noul": 0.1},
        },
        "usage": {"cost": 0.00001},
    }
    validate_response(good, {"c1", "none"})
    with pytest.raises(ProviderError):
        validate_response(good, {"c1", "c2"})
    del good["answers"]["pick"]["confidence"]
    with pytest.raises(ProviderError):
        validate_response(good, {"c1", "none"})


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("KRONERBENCH_LIVE") != "1", reason="Explicit opt-in needed for paid probes."
)
def test_live_contract():
    result = doctor()
    assert (
        result["key_valid"]
        and result["chat_tool_call"]
        and result["jev_snapshot"].startswith("typesafe/jev-")
    )
