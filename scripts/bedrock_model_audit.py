#!/usr/bin/env python3
"""Audit Bedrock TEXT/ON_DEMAND foundation models + inference profiles.

For each entry, augments the AWS catalog record with:
  - toolCalling: bool | null   — live converse() probe with a minimal toolConfig
  - probeError: str (optional) — error class/code when toolCalling is null
  - pricing: {input_per_1k, output_per_1k, currency, source}
                                 — looked up from AWS Pricing API
  - entryKind: "foundation-model" | "inference-profile"

Pricing is fetched regardless of probe outcome (so callers can see the cost of
a model even if their account can't currently invoke it).

Usage:
    uv run python scripts/bedrock_model_audit.py
    uv run python scripts/bedrock_model_audit.py --region us-west-2 --out audit.json
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

logger = logging.getLogger("bedrock_audit")

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


def _probe_tool_calling(model_id: str, region: str) -> tuple[bool | None, str | None]:
    """Live probe via bedrock-runtime converse. Returns (toolCalling, probeError).

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


def _extract_on_demand_price(product: dict[str, Any]) -> float | None:
    terms = product.get("terms", {}).get("OnDemand", {})
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            usd = dim.get("pricePerUnit", {}).get("USD")
            if usd is not None:
                try:
                    return float(usd)
                except (TypeError, ValueError):
                    pass
    return None


def _fetch_all_bedrock_pricing(target_region: str) -> dict[str, dict[str, float]]:
    """Return {lowercase_model_name: {input_per_1k, output_per_1k}}.

    Filters by ``regionCode`` so prices match the target Bedrock region.
    Best-effort — returns empty dict on failure.
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
                usage_type = attributes.get("usagetype", "").lower()
                feature = (attributes.get("feature") or "").lower()
                if "inp" in usage_type or "input" in feature:
                    kind = "input_per_1k"
                elif "otp" in usage_type or "output" in feature:
                    kind = "output_per_1k"
                else:
                    continue
                price = _extract_on_demand_price(product)
                if price is None:
                    continue
                out.setdefault(model_name.lower(), {})[kind] = price
    except (ClientError, BotoCoreError) as exc:
        logger.warning("AWS Pricing API call failed: %s", exc)
        return {}
    return out


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
        # Strip a leading "us." or "eu." cross-region inference prefix
        for prefix in ("us.", "eu.", "apac."):
            if mid.startswith(prefix):
                candidates.append(mid[len(prefix):])
                candidates.append(mid[len(prefix):].split(":")[0])
    for m in entry.get("models", []) or []:
        arn = (m.get("modelArn") or "").lower()
        if arn:
            candidates.append(arn.split("/")[-1])
    # De-duplicate while preserving order
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
) -> dict[str, Any]:
    """Return a pricing dict for ``entry``, best-effort matched against pricing_map."""
    candidates = _build_pricing_candidates(entry)
    chosen: dict[str, float] | None = None
    # Exact match first
    for cand in candidates:
        if cand in pricing_map:
            chosen = pricing_map[cand]
            break
    # Substring fallback
    if chosen is None:
        for key, value in pricing_map.items():
            if any(cand and (cand in key or key in cand) for cand in candidates):
                chosen = value
                break
    return {
        "input_per_1k": (chosen or {}).get("input_per_1k"),
        "output_per_1k": (chosen or {}).get("output_per_1k"),
        "currency": "USD",
        "source": "aws-pricing-api",
    }


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
    p.add_argument("--out", default=Path("bedrock-models.json"), type=Path)
    p.add_argument("--concurrency", type=int, default=8)
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
    pricing_map = _fetch_all_bedrock_pricing(args.region)
    print(f"Loaded pricing for {len(pricing_map)} model names.", file=sys.stderr)

    print(
        f"Probing {len(entries)} entries (concurrency={args.concurrency})...",
        file=sys.stderr,
    )
    probe_results = asyncio.run(_probe_all(entries, args.region, args.concurrency))

    augmented: list[dict[str, Any]] = []
    n_tool = n_priced = n_access_denied = 0
    for entry, (tool_calling, probe_error) in zip(entries, probe_results, strict=True):
        record = dict(entry)
        record["entryKind"] = _entry_kind(entry)
        record["toolCalling"] = tool_calling
        if probe_error is not None:
            record["probeError"] = probe_error
        record["pricing"] = _attach_pricing(entry, pricing_map)
        augmented.append(record)
        if tool_calling is True:
            n_tool += 1
        if record["pricing"]["input_per_1k"] is not None:
            n_priced += 1
        if probe_error == "AccessDenied":
            n_access_denied += 1

    args.out.write_text(
        json.dumps(augmented, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(augmented)} models to {args.out}; "
        f"{n_tool} tool-calling, {n_priced} priced, {n_access_denied} access-denied"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
