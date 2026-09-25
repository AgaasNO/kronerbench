"""Multi-field, bounded tool loop. Commitments are immutable within a trial."""

import time
from typing import Any

from kronerbench.cases.model import Case
from kronerbench.conditions.core import error_message, prompt, property_name, schema, validate
from kronerbench.config import decode_arguments, digest, dumps
from kronerbench.parsers.extract import extract
from kronerbench.providers.cache import Cache
from kronerbench.providers.fake import respond
from kronerbench.providers.openrouter import ProviderError, Transport
from kronerbench.providers.openrouter_decisions import request_body, validate_response


async def trial(
    case: Case,
    model: dict[str, Any],
    condition: str,
    repeat: int,
    options: dict[str, Any],
    cache: Cache,
    transport: Transport | None,
) -> dict[str, Any]:
    seed = options["seed"] + repeat
    candidates = extract(case.source, seed, case.kind)
    trial_id = digest([case.id, model["id"], condition, repeat, seed])[:24]
    record: dict[str, Any] = dict(
        schema_version="1.0",
        trial_id=trial_id,
        case_id=case.id,
        model=model["id"],
        condition=condition,
        repeat=repeat,
        seed=seed,
        attempts=[],
        results={},
        turns=0,
        latency_ms=0,
        cost_usd=0,
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        generation_ids=[],
        providers=[],
        resolved_snapshots=[],
        candidates=[c.to_dict() for c in candidates],
        request_keys=[],
        api_error=None,
        skip_reason=None,
        extractor_miss=[
            name
            for name, f in case.fields.items()
            if f.expected is not None and f.expected not in [c.value for c in candidates]
        ],
    )
    if condition == "select" and (case.suite in ["words", "derived"] or len(candidates) > 20):
        record["skip_reason"] = (
            "not_applicable" if case.suite in ["words", "derived"] else "too_many_candidates"
        )
        return record
    if condition == "strict_constrained" and not model.get("structured_outputs", False):
        record["skip_reason"] = "structured_outputs_not_supported"
        return record
    pending = list(case.fields)
    counts = dict.fromkeys(pending, 0)
    user = case.source + "\n\n" + case.instruction + "\nFields: " + ", ".join(case.fields)
    if condition == "select":
        user += (
            "\nCandidates: "
            + dumps([c.to_dict() for c in candidates])
            + "\nnone_of_these: absent or uncertain"
        )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": prompt(case, condition, options["prompt_lang"])},
        {"role": "user", "content": user},
    ]
    started = time.monotonic()

    async def fetch(body: dict[str, Any], path: str = "/api/v1/chat/completions") -> dict[str, Any]:
        request = {"path": path, "body": body}
        response = None if options["no_cache"] else cache.get(request)
        cached = response is not None
        if response is None:
            if model["id"].startswith("fake/"):
                response = respond(
                    case, condition, model["id"], record["turns"], pending, candidates, seed
                )
            else:
                assert transport is not None
                response = await transport.request(path, body, model["pricing"])
            cache.put(request, response)
        record["request_keys"].append(digest(request))
        usage = response.get("usage", {})
        record["cost_usd"] += float(usage.get("cost", 0)) if not cached else 0
        record.setdefault("cached_cost_usd", 0)
        record["cached_cost_usd"] += float(usage.get("cost", 0)) if cached else 0
        record["input_tokens"] += usage.get("prompt_tokens", usage.get("input_tokens", 0))
        record["output_tokens"] += usage.get("completion_tokens", usage.get("output_tokens", 0))
        record["reasoning_tokens"] += usage.get("completion_tokens_details", {}).get(
            "reasoning_tokens", 0
        )
        record["generation_ids"].append(response.get("id", ""))
        record["providers"].append(response.get("provider", "unknown"))
        record["resolved_snapshots"].append(response.get("model", model["id"]))
        return response

    try:
        if model.get("group") == "decision":
            for field in pending:
                body = request_body(case, field, candidates, model["resolved_id"])
                response = await fetch(body, "/api/alpha/decisions")
                validate_response(response, {c.id for c in candidates} | {"none_of_these"})
                pick = response["answers"]["pick"]
                ambiguous = response["answers"]["ambiguous"]["noul"]
                choice = next((c for c in candidates if c.id == pick["choice"]), None)
                record["results"][field] = {
                    "action": "record"
                    if choice and pick["confidence"] >= 0.85 and ambiguous < 0.5
                    else "flag",
                    "value": choice.value if choice else None,
                    "currency": None,
                    "jev_choice": pick["choice"],
                    "jev_confidence": pick["confidence"],
                    "jev_probs": pick["probabilities"],
                    "jev_ambiguous": ambiguous,
                    "jev_candidate_value": choice.value if choice else None,
                }
                record["attempts"].append(
                    {
                        "field": field,
                        "turn": 0,
                        "name": "decision",
                        "raw_arguments": dumps(response["answers"]),
                        "accepted": True,
                        "reason": "",
                        "value": choice.value if choice else None,
                    }
                )
            record["turns"] = 1
        else:
            for turn in range(6):
                if not pending:
                    break
                record["turns"] = turn
                body = {
                    "model": model.get("resolved_id", model["id"])
                    + (
                        ":exacto"
                        if options["exacto"] and not model["id"].startswith("fake/")
                        else ""
                    ),
                    "messages": messages,
                    "tools": schema(case, condition, candidates),
                    "tool_choice": "required",
                    "max_tokens": 4000,
                    "provider": {"require_parameters": True},
                }
                params = model.get(
                    "parameters", ["temperature", "seed", "reasoning", "tool_choice"]
                )
                if "temperature" in params:
                    body["temperature"] = 0
                if "seed" in params:
                    body["seed"] = seed
                if "reasoning" in params and model.get("reasoning"):
                    body["reasoning"] = {"effort": model["reasoning"]}
                if "tool_choice" not in params:
                    body["tool_choice"] = "auto"
                response = await fetch(body)
                message = response["choices"][0]["message"]
                # Preserve reasoning_details and every other assistant field unchanged.
                messages.append(message)
                calls = message.get("tool_calls", [])
                if not calls:
                    for field in pending:
                        record["results"][field] = {"action": "no_call"}
                    break
                for call in calls:
                    function = call["function"]
                    name = function["name"]
                    raw = function["arguments"]
                    accepted = False
                    reason = ""
                    value = None
                    field = None
                    args = {}
                    try:
                        args = decode_arguments(raw)
                        field = args.get("field")
                        if field not in pending:
                            reason = "unknown, completed or exhausted field"
                        elif (
                            name == "flag_for_review"
                            and set(args) == {"field", "reason"}
                            and isinstance(args["reason"], str)
                        ):
                            accepted = True
                            record["results"][field] = {"action": "flag"}
                        elif (
                            name == "record_amount"
                            and condition == "select"
                            and args.get("candidate_id") == "none_of_these"
                            and set(args) == {"field", "candidate_id"}
                        ):
                            accepted = True
                            record["results"][field] = {"action": "flag"}
                        elif name == "record_amount":
                            verdict = validate(case, condition, args, candidates)
                            accepted, reason, value = (
                                verdict.accepted,
                                verdict.reason,
                                verdict.value,
                            )
                            if accepted:
                                record["results"][field] = {
                                    "action": "record",
                                    "value": value,
                                    "currency": args.get("currency"),
                                }
                        else:
                            reason = "invalid tool or flag arguments"
                    except (ValueError, TypeError, KeyError) as e:
                        reason = str(e)
                    record["attempts"].append(
                        {
                            "field": field,
                            "turn": turn,
                            "name": name,
                            "raw_arguments": raw,
                            "accepted": accepted,
                            "reason": reason,
                            "value": value,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": "Recorded."
                            if accepted
                            else error_message(
                                args.get(property_name(case, condition), raw),
                                reason,
                                options["error_style"],
                            ),
                        }
                    )
                    if field in pending:
                        counts[field] += 1
                        if accepted or counts[field] > options["max_retries"]:
                            pending.remove(field)
                record["turns"] = turn + 1
            for field in case.fields:
                record["results"].setdefault(field, {"action": "exhausted"})
        if options.get("verify") == "jev" and condition != "select" and transport is not None:
            verifier = options["verifier_model"]
            for field, result in record["results"].items():
                if result["action"] != "record":
                    continue
                body = {
                    "model": verifier["resolved_id"],
                    "state": {"source": case.source},
                    "questions": {
                        "correct": {
                            "type": "noul",
                            "instructions": f"The source states the {field} is {result['value']} {'minor units' if case.kind == 'amount' else case.kind}.",
                        }
                    },
                }
                response = await transport.request(
                    "/api/alpha/decisions", body, verifier["pricing"]
                )
                cache.put({"path": "/api/alpha/decisions", "body": body}, response)
                result["verifier_noul"] = response["answers"]["correct"]["noul"]
                record["cost_usd"] += response["usage"]["cost"]
    except (ProviderError, KeyError, IndexError, TypeError) as e:
        record["api_error"] = str(e)
        for field in case.fields:
            record["results"].setdefault(field, {"action": "api_error"})
    record["latency_ms"] = (time.monotonic() - started) * 1000
    return record
