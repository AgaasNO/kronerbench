"""OpenRouter transport and capability discovery, isolated from experimental logic."""

import asyncio
import os
import random
import subprocess
from decimal import Decimal
from typing import Any, cast

import httpx
import yaml

from kronerbench.config import ROOT, dumps, write_json
from kronerbench.providers.costguard import CostGuard

BASE = "https://openrouter.ai"


class CredentialsError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


def key() -> str:
    value = os.environ.get("OPENROUTER_API_KEY", "")
    if not value:
        raise CredentialsError(
            "OPENROUTER_API_KEY is not set. Create one at https://openrouter.ai/settings/keys and export it."
        )
    return value


def configured() -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]], yaml.safe_load((ROOT / "config/models.yaml").read_text())["models"]
    )


async def discover(group: str = "") -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(BASE + "/api/v1/models")
        response.raise_for_status()
        catalog = {m["id"]: m for m in response.json()["data"]}

        async def one(model: dict[str, Any]) -> dict[str, Any]:
            requested = model["id"]
            r = await client.get(BASE + "/api/v1/models/" + requested + "/endpoints")
            if r.status_code == 404 or (r.status_code == 200 and not r.json().get("data", {}).get("endpoints")):
                # Latest aliases can be absent from the endpoints path; resolve within the same family.
                family = requested.removeprefix("~").removesuffix("-latest")
                options = [m for name, m in catalog.items() if name.startswith(family) and ":" not in name and not name.startswith("~")]
                if not options:
                    raise ProviderError(
                        f"Model {requested} is unavailable and has no obvious family replacement."
                    )
                resolved = max(options, key=lambda m: m.get("created", 0))["id"]
                r = await client.get(BASE + "/api/v1/models/" + resolved + "/endpoints")
            r.raise_for_status()
            data = r.json()["data"]
            endpoints = [e for e in data.get("endpoints", []) if e.get("status", 0) == 0]
            if not endpoints:
                raise ProviderError(f"No active endpoints for {requested}.")
            supported = set.intersection(
                *(set(e.get("supported_parameters", [])) for e in endpoints)
            )
            union = set.union(*(set(e.get("supported_parameters", [])) for e in endpoints))
            return {
                **model,
                "requested_id": requested,
                "resolved_id": data["id"],
                "parameters": sorted(union),
                "common_parameters": sorted(supported),
                "endpoints": endpoints,
                "pricing": {
                    "prompt": str(max(Decimal(e["pricing"]["prompt"]) for e in endpoints)),
                    "completion": str(max(Decimal(e["pricing"]["completion"]) for e in endpoints)),
                },
                "tools": model["group"] == "decision" or "tools" in union,
                "structured_outputs": "structured_outputs" in union,
            }

        models = await asyncio.gather(
            *(one(m) for m in configured() if not group or m["group"] == group)
        )
    write_json(ROOT / ".cache/models.json", models)
    return list(models)


class Transport:
    def __init__(self, guard: CostGuard):
        self.guard = guard
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=20))
        self.downgrades: list[dict[str, Any]] = []

    async def close(self) -> None:
        await self.client.aclose()

    async def request(
        self, path: str, body: dict[str, Any], pricing: dict[str, str]
    ) -> dict[str, Any]:
        headers = {
            "Authorization": "Bearer " + key(),
            "HTTP-Referer": "https://github.com/AgaasNO/kronerbench",
            "X-Title": "KronerBench",
        }
        price_in, price_out = Decimal(pricing["prompt"]), Decimal(pricing["completion"])
        maximum = (
            Decimal(len(dumps(body).encode())) * price_in
            + Decimal(body.get("max_tokens", 4000)) * price_out
        )
        downgraded = set()
        for attempt in range(5):
            await self.guard.reserve(maximum)
            try:
                response = await self.client.post(BASE + path, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError):
                # Unknown billing after transport failure is conservatively charged at the reserved ceiling.
                await self.guard.settle(maximum, maximum)
                if attempt == 4:
                    raise ProviderError(
                        "Transport failed after five tries; uncertain billing charged at request ceiling."
                    ) from None
                await asyncio.sleep(min(2**attempt + random.random(), 15))
                continue
            if response.status_code in (401, 402):
                await self.guard.settle(maximum, Decimal(0))
                raise CredentialsError(
                    f"OpenRouter returned {response.status_code}; fix the API key or add credits."
                )
            if response.status_code == 400:
                await self.guard.settle(maximum, Decimal(0))
                message = response.text.lower()
                parameter = next(
                    (
                        p
                        for p in ["tool_choice", "temperature", "seed", "reasoning"]
                        if p in message and p in body and p not in downgraded
                    ),
                    None,
                )
                if parameter is not None:
                    downgraded.add(parameter)
                    old = body[parameter]
                    if parameter == "tool_choice":
                        body[parameter] = "auto"
                    else:
                        body.pop(parameter)
                    self.downgrades.append(
                        {
                            "model": body["model"],
                            "parameter": parameter,
                            "requested": old,
                            "actual": body.get(parameter),
                        }
                    )
                    continue
                raise ProviderError(f"Unsupported request: {response.text[:500]}")
            if response.status_code == 429 or response.status_code >= 500:
                await self.guard.settle(maximum, Decimal(0))
                if attempt < 4:
                    await asyncio.sleep(min(2**attempt + random.random(), 15))
                    continue
            if response.is_error:
                await self.guard.settle(maximum, Decimal(0))
                raise ProviderError(f"Provider HTTP {response.status_code}: {response.text[:300]}")
            data = response.json()
            if "error" in data:
                await self.guard.settle(maximum, Decimal(str(data.get("usage", {}).get("cost", 0))))
                raise ProviderError(f"Provider response error: {data['error']}")
            if "cost" not in data.get("usage", {}):
                await self.guard.settle(maximum, maximum)
                raise ProviderError(
                    "Response lacks usage.cost; billed conservatively and rejected."
                )
            await self.guard.settle(maximum, Decimal(str(data["usage"]["cost"])))
            return cast(dict[str, Any], data)
        raise ProviderError("Request failed after parameter downgrades.")


def doctor() -> dict[str, Any]:
    async def probe() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(BASE + "/api/v1/key", headers={"Authorization": "Bearer " + key()})
            if r.status_code in (401, 402):
                raise CredentialsError(
                    f"OpenRouter returned {r.status_code}. Fix the key or credits."
                )
            r.raise_for_status()
            credits = r.json()["data"].get("limit_remaining")
        models = await discover()
        cheap = min(
            (m for m in models if m["group"] not in ["decision", "frontier-xl"] and m["tools"]),
            key=lambda m: Decimal(m["pricing"]["prompt"]) + Decimal(m["pricing"]["completion"]),
        )
        guard = CostGuard(0.1)
        transport = Transport(guard)
        try:
            chat = await transport.request(
                "/api/v1/chat/completions",
                {
                    "model": cheap["resolved_id"],
                    "messages": [
                        {"role": "user", "content": "Call record_amount with amount 100,00."}
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "record_amount",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"amount": {"type": "string"}},
                                    "required": ["amount"],
                                },
                            },
                        }
                    ],
                    "tool_choice": "required",
                    "max_tokens": 256,
                },
                cheap["pricing"],
            )
            jev = next(m for m in models if m["group"] == "decision")
            decision = await transport.request(
                "/api/alpha/decisions",
                {
                    "model": jev["resolved_id"],
                    "state": {"document": "Total NOK 100,00"},
                    "questions": {
                        "pick": {
                            "type": "choice",
                            "instructions": "Choose the total.",
                            "criteria": {"c1": "100 NOK", "c2": "200 NOK"},
                        },
                        "ambiguous": {
                            "type": "noul",
                            "instructions": "The total cannot be determined.",
                        },
                    },
                },
                jev["pricing"],
            )
            from kronerbench.providers.openrouter_decisions import validate_response

            validate_response(decision, {"c1", "c2"})
            return {
                "key_valid": True,
                "remaining": credits,
                "chat_tool_call": bool(chat["choices"][0]["message"].get("tool_calls")),
                "jev_snapshot": decision["model"],
                "probe_cost": str(guard.spent),
                "github": subprocess.run(["gh", "auth", "status"], capture_output=True).returncode
                == 0,
            }
        finally:
            await transport.close()

    result = asyncio.run(probe())
    write_json(ROOT / ".cache/doctor.json", result)
    return result
