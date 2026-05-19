#!/usr/bin/env python3
"""Audit Bedrock TEXT/ON_DEMAND foundation models + inference profiles.

For each entry, augments the AWS catalog record with:
  - toolCallingSupported: bool | null   — live converse() probe with a minimal
                                          toolConfig (null when the probe could
                                          not run)
  - toolProbeError: str | null          — error class/code when the probe
                                          failed; null on success
  - pricing: {input_per_1m, output_per_1m, currency, source}
                                          — looked up from AWS Pricing API,
                                          normalised to USD per 1,000,000 tokens
  - pricingProbeError: str | null       — "NotFoundInPricingAPI" when no SKU
                                          matched, or the upstream Pricing API
                                          error class on global fetch failure
  - entryKind: "foundation-model" | "inference-profile"

Output: two JSON array files in the same directory:
  - bedrock-models-available.json   (always written; models you can invoke)
  - bedrock-models-unavailable.json (only with --all; AccessDenied probes)

"Available" means the converse() probe did not return AccessDeniedException.
Other probe failures (ValidationException, etc.) still count as available
because the model accepted credentialed traffic — it just rejected this
particular request shape.

Pricing is fetched regardless of probe outcome (Bedrock invocation access and
the AWS Pricing API are independent services).

Usage:
    uv run python scripts/bedrock_model_audit.py
    uv run python scripts/bedrock_model_audit.py --all
    uv run python scripts/bedrock_model_audit.py --region us-west-2 --out-dir ./audit
    uv run python scripts/bedrock_model_audit.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from decimal import Decimal

logger = logging.getLogger("bedrock_audit")


class _DecimalFloatEncoder(json.JSONEncoder):
    """JSON encoder that emits floats in decimal notation, never scientific.

    Default ``json.dumps`` emits small floats like ``8e-07``; this overrides the
    float-serialization hook in ``json.encoder._make_iterencode`` so the output
    stays human-readable for small per-token prices. Routes through
    ``Decimal(repr(x))`` so the result is the shortest round-tripping decimal
    representation — no IEEE 754 long-tail artifacts like ``0.80000000000…04``.
    """

    def iterencode(self, o, _one_shot=False):  # type: ignore[override]
        from json.encoder import (  # noqa: PLC0415
            _make_iterencode,
            encode_basestring,
            encode_basestring_ascii,
        )

        def floatstr(x: float) -> str:
            if x != x:
                return "NaN"
            if x == float("inf"):
                return "Infinity"
            if x == float("-inf"):
                return "-Infinity"
            # repr() gives the shortest representation that round-trips through
            # float(); Decimal(...) parses it; format(d, "f") forces decimal
            # (never scientific) output.
            s = format(Decimal(repr(x)), "f")
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            return s if s else "0"

        encoder = encode_basestring_ascii if self.ensure_ascii else encode_basestring
        _iterencode = _make_iterencode(
            {},
            self.default,
            encoder,
            self.indent,
            floatstr,
            self.key_separator,
            self.item_separator,
            self.sort_keys,
            self.skipkeys,
            _one_shot,
        )
        return _iterencode(o, 0)

# AWS Pricing API runs in us-east-1 / ap-south-1 only. us-east-1 covers all
# Bedrock regions — pass the target region as a filter, not the endpoint region.
_PRICING_ENDPOINT_REGION = "us-east-1"

# Trivial tool definition — keeps probe cost to ~50 input / ~20 output tokens.
_PROBE_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_time",
                "description": "Returns the current time. Call this to test tool use.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    }
                },
            }
        }
    ],
    "toolChoice": {"auto": {}},
}

_PROBE_MESSAGES = [
    {
        "role": "user",
        "content": [{"text": "Use the get_time tool to fetch the current time."}],
    }
]

_PROBE_INFERENCE_CONFIG = {"maxTokens": 50, "temperature": 0.0}


def _list_foundation_models(region: str) -> list[dict[str, Any]]:
    bedrock = boto3.client("bedrock", region_name=region)
    resp = bedrock.list_foundation_models(
        byOutputModality="TEXT",
        byInferenceType="ON_DEMAND",
    )
    return list(resp.get("modelSummaries", []))


def _list_inference_profiles(region: str) -> list[dict[str, Any]]:
    bedrock = boto3.client("bedrock", region_name=region)
    profiles: list[dict[str, Any]] = []
    paginator = bedrock.get_paginator("list_inference_profiles")
    for page in paginator.paginate():
        profiles.extend(page.get("inferenceProfileSummaries", []))
    return profiles


def _entry_id(entry: dict[str, Any]) -> str:
    """Return modelId for foundation models, inferenceProfileId for profiles."""
    return entry.get("modelId") or entry.get("inferenceProfileId") or ""


def _entry_kind(entry: dict[str, Any]) -> str:
    return "foundation-model" if "modelId" in entry else "inference-profile"


def _provider_of(
    entry: dict[str, Any],
    canonical_by_prefix: dict[str, str] | None = None,
) -> str:
    """Return a provider name suitable for sorting.

    Foundation models carry ``providerName`` directly (AWS-canonical casing
    like ``DeepSeek``, ``AI21 Labs``). Inference profiles don't — derive the
    provider from the inferenceProfileId by stripping the cross-region prefix
    (``us.``, ``eu.``, ``apac.``, ``global.``) and taking the segment before
    the first dot. If a ``canonical_by_prefix`` map of foundation-model
    prefixes → provider names is supplied (built from the foundation-model
    list), reuse AWS's casing so profiles match their underlying models;
    otherwise title-case the prefix as a last-resort.
    """
    name = entry.get("providerName")
    if name:
        return name
    mid = (entry.get("inferenceProfileId") or "").lower()
    for prefix in ("us.", "eu.", "apac.", "global."):
        if mid.startswith(prefix):
            mid = mid[len(prefix):]
            break
    if not mid:
        return "Unknown"
    head = mid.split(".", 1)[0]
    if not head:
        return "Unknown"
    if canonical_by_prefix and head in canonical_by_prefix:
        return canonical_by_prefix[head]
    return head.title()


def _build_canonical_provider_map(
    foundation_models: list[dict[str, Any]],
) -> dict[str, str]:
    """Return {modelid_prefix: AWS-canonical providerName} from foundation models.

    Lets inference-profile records inherit AWS's casing (``Anthropic``,
    ``DeepSeek``, ``AI21 Labs``) instead of falling back to ``str.title``,
    which produces inconsistent variants like ``Deepseek``.
    """
    out: dict[str, str] = {}
    for fm in foundation_models:
        mid = (fm.get("modelId") or "").lower()
        provider = fm.get("providerName")
        if not mid or not provider:
            continue
        prefix = mid.split(".", 1)[0]
        if prefix and prefix not in out:
            out[prefix] = provider
    return out


def _probe_tool_calling(model_id: str, region: str) -> tuple[bool | None, str | None]:
    """Live probe via bedrock-runtime converse. Returns (toolCallingSupported, toolProbeError).

    Semantics:
      - HTTP 200 with toolUse content block → True, None
      - HTTP 200 without toolUse but model accepted toolConfig → True, None
        (API-level acceptance of toolConfig is the definition of "supports tool calling")
      - ValidationException mentioning tool/toolConfig → False, None
        (model rejected toolConfig — explicit signal that tool calling is unsupported)
      - AccessDeniedException → None, "AccessDenied"
      - Any other ClientError → None, <error code>
      - Any BotoCoreError or unexpected exception → None, <class name>
    """
    runtime = boto3.client("bedrock-runtime", region_name=region)
    try:
        resp = runtime.converse(
            modelId=model_id,
            messages=_PROBE_MESSAGES,
            inferenceConfig=_PROBE_INFERENCE_CONFIG,
            toolConfig=_PROBE_TOOL_CONFIG,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = (exc.response.get("Error", {}).get("Message") or "").lower()
        if code == "AccessDeniedException":
            return None, "AccessDenied"
        if code == "ValidationException" and (
            "tool" in msg or "toolconfig" in msg or "tools" in msg
        ):
            return False, None
        return None, code
    except BotoCoreError as exc:
        return None, type(exc).__name__
    except Exception as exc:  # noqa: BLE001
        return None, type(exc).__name__

    content = resp.get("output", {}).get("message", {}).get("content", [])
    has_tool_use = any("toolUse" in block for block in content)
    if has_tool_use or resp.get("stopReason") == "tool_use":
        return True, None
    # Model accepted toolConfig but chose not to call the tool. The API-level
    # acceptance is what we're measuring — return True.
    return True, None


def _extract_on_demand_price(product: dict[str, Any]) -> tuple[Decimal, str] | None:
    """Return (price, unit) of the first OnDemand price dimension, or None.

    Price returned as ``Decimal`` (parsed directly from the AWS string) to avoid
    float-multiplication artifacts during the per-1K → per-1M conversion.
    """
    terms = product.get("terms", {}).get("OnDemand", {})
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            usd = dim.get("pricePerUnit", {}).get("USD")
            unit = dim.get("unit") or ""
            if usd is not None:
                try:
                    return Decimal(str(usd)), unit
                except Exception:  # noqa: BLE001
                    pass
    return None


# Anything in this set in a usagetype means "not the standard on-demand
# inference SKU we want for sweep cost estimation."
_SKU_SKIP_MARKERS: tuple[str, ...] = (
    "image", "cache", "customization", "custom-model",
    "batch", "flex", "priority", "archival", "provisioned",
    "storage", "automatedreasoning", "guardrail",
    "evaluation", "agent", "training", "embedding",
)


def _classify_sku(usage_type: str, unit: str) -> str | None:
    """Return 'input_per_1m', 'output_per_1m', or None to skip.

    Recognises both modern (``*-input-tokens`` / ``*-output-tokens``, with the
    standard on-demand tier as the bare suffix) and legacy (``Inp-`` / ``Otp-``)
    Bedrock SKU naming. Filters out non-inference, non-standard, and
    non-token-priced SKUs.
    """
    u = usage_type.lower()
    if "tokens" not in unit.lower():
        return None
    if any(marker in u for marker in _SKU_SKIP_MARKERS):
        return None
    if "output-tokens" in u or "-otp-" in u or u.endswith("otp"):
        return "output_per_1m"
    if "input-tokens" in u or "-inp-" in u or u.endswith("inp"):
        return "input_per_1m"
    return None


def _fetch_all_bedrock_pricing(
    target_region: str,
) -> tuple[dict[str, dict[str, float]], str | None]:
    """Return ({lowercase_model_name: {input_per_1m, output_per_1m}}, error).

    Filters by ``regionCode`` so prices match the target Bedrock region. Always
    converts to USD per 1,000,000 tokens. On failure returns ({}, "<ErrorName>")
    so the caller can propagate the error into per-record pricingProbeError.
    """
    pricing = boto3.client("pricing", region_name=_PRICING_ENDPOINT_REGION)
    out: dict[str, dict[str, float]] = {}
    try:
        paginator = pricing.get_paginator("get_products")
        pages = paginator.paginate(
            ServiceCode="AmazonBedrock",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "regionCode", "Value": target_region},
            ],
        )
        for page in pages:
            for raw in page.get("PriceList", []):
                product = json.loads(raw) if isinstance(raw, str) else raw
                attributes = product.get("product", {}).get("attributes", {})
                model_name = (
                    attributes.get("model")
                    or attributes.get("titleDescription")
                    or ""
                ).strip()
                if not model_name:
                    continue
                usage_type = attributes.get("usagetype", "")
                extracted = _extract_on_demand_price(product)
                if extracted is None:
                    continue
                price, unit = extracted
                kind = _classify_sku(usage_type, unit)
                if kind is None:
                    continue
                # AWS Bedrock token SKUs report unit as "1K tokens" almost
                # universally. Normalise to per-1M with Decimal arithmetic so
                # the conversion is exact — multiplying a parsed Decimal by
                # Decimal('1000') gives clean values like 0.06 instead of the
                # 0.060000000000000005 float artefact.
                u = unit.lower()
                if "1k" in u or "1,000 tokens" in u or "1000 tokens" in u:
                    price_per_1m_d = price * Decimal("1000")
                else:
                    price_per_1m_d = price * Decimal("1000000")
                out.setdefault(model_name.lower(), {})[kind] = float(price_per_1m_d)
    except (ClientError, BotoCoreError) as exc:
        err = type(exc).__name__
        logger.warning("AWS Pricing API call failed: %s (%s)", exc, err)
        return {}, err
    return out, None


def _build_pricing_candidates(entry: dict[str, Any]) -> list[str]:
    """Build a list of candidate lookup keys for matching against the pricing map."""
    candidates: list[str] = []
    for name_field in ("modelName", "inferenceProfileName"):
        name = entry.get(name_field) or ""
        if name:
            candidates.append(name.lower())
    mid = _entry_id(entry).lower()
    if mid:
        candidates.append(mid)
        candidates.append(mid.split(":")[0])
        candidates.append(mid.split("/")[-1])
        for prefix in ("us.", "eu.", "apac.", "global."):
            if mid.startswith(prefix):
                stripped = mid[len(prefix):]
                candidates.append(stripped)
                candidates.append(stripped.split(":")[0])
    for m in entry.get("models", []) or []:
        arn = (m.get("modelArn") or "").lower()
        if arn:
            candidates.append(arn.split("/")[-1])
    # De-duplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _attach_pricing(
    entry: dict[str, Any],
    pricing_map: dict[str, dict[str, float]],
    global_pricing_error: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Return (pricing_dict, pricingProbeError).

    pricing_dict always has the same keys (input_per_1m, output_per_1m,
    currency, source) with prices possibly null. pricingProbeError is:
      - the global Pricing API error if the upstream fetch failed
      - "NotFoundInPricingAPI" if no SKU matched
      - None on a successful lookup
    """
    if global_pricing_error is not None:
        return (
            {
                "input_per_1m": None,
                "output_per_1m": None,
                "currency": "USD",
                "source": "aws-pricing-api",
            },
            global_pricing_error,
        )

    candidates = _build_pricing_candidates(entry)
    chosen: dict[str, float] | None = None
    for cand in candidates:
        if cand in pricing_map:
            chosen = pricing_map[cand]
            break
    if chosen is None:
        for key, value in pricing_map.items():
            if any(cand and (cand in key or key in cand) for cand in candidates):
                chosen = value
                break

    pricing = {
        "input_per_1m": (chosen or {}).get("input_per_1m"),
        "output_per_1m": (chosen or {}).get("output_per_1m"),
        "currency": "USD",
        "source": "aws-pricing-api",
    }
    error = None if chosen is not None else "NotFoundInPricingAPI"
    return pricing, error


async def _probe_all(
    entries: list[dict[str, Any]],
    region: str,
    concurrency: int,
) -> list[tuple[bool | None, str | None]]:
    sem = asyncio.Semaphore(concurrency)

    async def one(entry: dict[str, Any]) -> tuple[bool | None, str | None]:
        mid = _entry_id(entry)
        async with sem:
            return await asyncio.to_thread(_probe_tool_calling, mid, region)

    return await asyncio.gather(*[one(e) for e in entries])


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Audit Bedrock foundation models + inference profiles for "
            "tool-calling capability and pricing."
        )
    )
    p.add_argument("--region", default="us-east-1")
    p.add_argument(
        "--out-dir",
        default=Path("."),
        type=Path,
        help="Directory for output files (default: current dir).",
    )
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument(
        "--all",
        action="store_true",
        help="Also write bedrock-models-unavailable.json for AccessDenied models.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print model IDs that would be probed and exit without invoking Bedrock or Pricing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _build_arg_parser().parse_args(argv)

    print(
        f"Listing foundation models + inference profiles in {args.region}...",
        file=sys.stderr,
    )
    foundation = _list_foundation_models(args.region)
    profiles = _list_inference_profiles(args.region)
    entries = foundation + profiles
    print(
        f"Found {len(foundation)} foundation models + {len(profiles)} inference "
        f"profiles = {len(entries)} total.",
        file=sys.stderr,
    )

    if args.dry_run:
        for e in entries:
            print(f"{_entry_kind(e):<18} {_entry_id(e)}")
        return 0

    print("Fetching AWS Pricing API records...", file=sys.stderr)
    pricing_map, pricing_global_error = _fetch_all_bedrock_pricing(args.region)
    if pricing_global_error:
        print(
            f"WARN: AWS Pricing API fetch failed ({pricing_global_error}); "
            "all records will carry pricingProbeError.",
            file=sys.stderr,
        )
    else:
        print(f"Loaded pricing for {len(pricing_map)} model names.", file=sys.stderr)

    print(
        f"Probing {len(entries)} entries (concurrency={args.concurrency})...",
        file=sys.stderr,
    )
    probe_results = asyncio.run(_probe_all(entries, args.region, args.concurrency))

    canonical_providers = _build_canonical_provider_map(foundation)

    available: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    n_tool = n_priced = n_access_denied = 0
    for entry, (tool_supported, tool_probe_error) in zip(
        entries, probe_results, strict=True
    ):
        record = dict(entry)
        record["entryKind"] = _entry_kind(entry)
        record["providerName"] = _provider_of(entry, canonical_providers)
        record["toolCallingSupported"] = tool_supported
        record["toolProbeError"] = tool_probe_error
        pricing, pricing_probe_error = _attach_pricing(
            entry, pricing_map, pricing_global_error
        )
        record["pricing"] = pricing
        record["pricingProbeError"] = pricing_probe_error

        if tool_supported is True:
            n_tool += 1
        if pricing["input_per_1m"] is not None:
            n_priced += 1
        if tool_probe_error == "AccessDenied":
            n_access_denied += 1
            unavailable.append(record)
        else:
            available.append(record)

    def _sort_key(r: dict[str, Any]) -> tuple[str, str]:
        return (r.get("providerName") or "", _entry_id(r))

    available.sort(key=_sort_key)
    unavailable.sort(key=_sort_key)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    available_path = args.out_dir / "bedrock-models-available.json"
    available_path.write_text(
        json.dumps(available, indent=2, default=str, cls=_DecimalFloatEncoder) + "\n",
        encoding="utf-8",
    )

    summary = (
        f"Wrote {len(available)} available models to {available_path}; "
        f"{n_tool} tool-calling, {n_priced} priced, {n_access_denied} access-denied"
    )

    if args.all:
        unavailable_path = args.out_dir / "bedrock-models-unavailable.json"
        unavailable_path.write_text(
            json.dumps(unavailable, indent=2, default=str, cls=_DecimalFloatEncoder)
            + "\n",
            encoding="utf-8",
        )
        summary += f"; {len(unavailable)} unavailable written to {unavailable_path}"
    else:
        summary += f" ({len(unavailable)} unavailable suppressed; pass --all to write)"

    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
