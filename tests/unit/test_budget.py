import asyncio
from decimal import Decimal

import httpx
import pytest

from kronerbench.config import read_json
from kronerbench.providers.costguard import CostCap, CostGuard
from kronerbench.providers.openrouter import ProviderError, Transport, configured
from kronerbench.runner.scheduler import plan


def test_budget_profile_caps_spend_and_keeps_paired_cases():
    options, cases, models, conditions = plan({"profile": "budget"}, configured())
    assert options["max_cost"] == 5
    assert len(cases) == 240
    assert len({c.suite for c in cases}) == 12
    assert len(models) == 5
    assert conditions == ["strict", "lenient", "json_number", "select"]
    assert plan({"profile": "budget", "max_cost": 2}, configured())[0]["max_cost"] == 2
    assert plan({"profile": "budget", "max_cost": 200}, configured())[0]["max_cost"] == 5


def test_unsettled_requests_survive_restart_and_enforce_cap(tmp_path):
    async def run():
        ledger = tmp_path / "cost.json"
        first = CostGuard(5, ledger=ledger)
        await first.reserve(Decimal("3"))
        resumed = CostGuard(5, ledger=ledger)
        assert resumed.spent == Decimal("3")
        with pytest.raises(CostCap):
            await resumed.reserve(Decimal("2.01"))
        await resumed.reserve(Decimal("2"))
        await resumed.settle(Decimal("2"), Decimal("0.5"))
        assert read_json(ledger)["spent"] == "3.5"
        assert read_json(ledger)["reserved"] == "0"

    asyncio.run(run())


def test_repeated_server_errors_settle_each_reservation_once(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def no_sleep(_):
        pass

    monkeypatch.setattr("kronerbench.providers.openrouter.asyncio.sleep", no_sleep)

    async def run():
        guard = CostGuard(5)
        transport = Transport(guard)
        await transport.client.aclose()
        transport.client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(503))
        )
        try:
            with pytest.raises(ProviderError, match="five tries"):
                await transport.request(
                    "/test", {"model": "test"}, {"prompt": ".001", "completion": "0"}
                )
            assert guard.reserved == 0 and guard.spent == 0
        finally:
            await transport.close()

    asyncio.run(run())


def test_cancelled_request_retains_cost_ceiling(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def run():
        entered = asyncio.Event()

        async def respond(request):
            entered.set()
            await asyncio.Event().wait()

        guard = CostGuard(5, ledger=tmp_path / "cost.json")
        transport = Transport(guard)
        await transport.client.aclose()
        transport.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        task = asyncio.create_task(
            transport.request("/test", {"model": "test"}, {"prompt": ".001", "completion": "0"})
        )
        await entered.wait()
        reserved = guard.reserved
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert guard.reserved == 0 and guard.spent == reserved > 0
        await transport.close()

    asyncio.run(run())
