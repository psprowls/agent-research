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
import gzip
import html
import json
import logging
import re
import sys
import urllib.error
import urllib.request
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


# Catalog model-id → AWS Pricing API "model" attribute name. Hand-curated for
# cases where the marketing name AWS uses in pricing differs from the catalog
# ID in a way the fuzzy matcher can't bridge (e.g. dates dropped, version
# numbers rewritten, vendor prefix added/removed). Discovered via:
#   aws pricing get-products --service-code AmazonBedrock ... | jq '.model'
_PRICING_NAME_ALIASES: dict[str, str] = {
    "mistral.magistral-small-2509":        "Magistral Small 1.2",
    "mistral.ministral-3-3b-instruct":     "Ministral 3B 3.0",
    "mistral.ministral-3-8b-instruct":     "Ministral 8B 3.0",
    "mistral.ministral-3-14b-instruct":    "Ministral 14B 3.0",
    "mistral.voxtral-mini-3b-2507":        "Voxtral Mini 1.0",
    "mistral.voxtral-small-24b-2507":      "Voxtral Small 1.0",
    "nvidia.nemotron-nano-12b-v2":         "NVIDIA Nemotron Nano 2",
    "nvidia.nemotron-nano-9b-v2":          "NVIDIA Nemotron Nano 2",
    "nvidia.nemotron-nano-3-30b":          "Nemotron Nano 3 30B",
    "qwen.qwen3-coder-30b-a3b-v1:0":       "Qwen3 Coder 30B A3B",
    "amazon.nova-2-sonic-v1:0":            "Nova Sonic 2.0",
    "amazon.nova-2-lite-v1:0":             "Nova 2.0 Lite",
    "amazon.nova-2-pro-v1:0":              "Nova 2.0 Pro",
    "amazon.nova-2-omni-v1:0":             "Nova 2.0 Omni",
}


# Non-token-priced model classification. Tagged on the record as
# ``pricingKind`` so callers can tell why a record has null token prices
# (it's billed per-image / per-document / per-second, not per-token).
_PRICING_KIND_PATTERNS: dict[str, str] = {
    "stable-":  "image",      # Stability image gen / manipulation
    "rerank":   "rerank",     # Cohere rerank — per-document
    "embed":    "embedding",  # Cohere embed, TwelveLabs Marengo Embed
    "marengo":  "video",      # TwelveLabs Marengo — video understanding
    "pegasus":  "video",      # TwelveLabs Pegasus — video understanding
    "sonic":    "speech",     # Nova Sonic / Nova Sonic 2.0 — speech
}


def _classify_pricing_kind(entry: dict[str, Any]) -> str:
    """Classify the underlying pricing unit of an entry.

    Returns one of: ``tokens``, ``image``, ``embedding``, ``rerank``,
    ``video``, ``speech``. Used to tag records whose null token-pricing
    is expected (because the model is priced in different units).
    """
    eid = _entry_id(entry).lower()
    for pattern, kind in _PRICING_KIND_PATTERNS.items():
        if pattern in eid:
            return kind
    out_mods = {(m or "").upper() for m in entry.get("outputModalities") or []}
    if "EMBEDDING" in out_mods:
        return "embedding"
    if "IMAGE" in out_mods and "TEXT" not in out_mods:
        return "image"
    return "tokens"


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


# ---------------------------------------------------------------------------
# AWS Bedrock pricing-page scrape (opt-in via --scrape)
# ---------------------------------------------------------------------------
# The AWS Pricing API (boto3 `pricing` client) does NOT carry SKUs for the
# newer Anthropic Claude models (3.5/4.x) or for some recent inference-only
# profiles. The public pricing page at https://aws.amazon.com/bedrock/pricing/
# does — the prices are embedded as `{priceOf!namespace/namespace!ID}`
# placeholders inside escaped <table> chunks, resolved client-side against
# JSON files served from b0.p.awsstatic.com.
#
# This scraper performs the same resolution server-side so the audit can
# recover those missing prices.

_PRICING_PAGE_URL = "https://aws.amazon.com/bedrock/pricing/"
_PRICING_CDN_BASE = "https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps"
_PRICING_NAMESPACES: tuple[str, ...] = ("bedrock", "bedrockfoundationmodels")

# AWS region code → pricing-page display name. Add entries here as needed.
_REGION_DISPLAY_NAMES: dict[str, str] = {
    "us-east-1":      "US East (N. Virginia)",
    "us-east-2":      "US East (Ohio)",
    "us-west-2":      "US West (Oregon)",
    "us-west-1":      "US West (N. California)",
    "eu-central-1":   "EU (Frankfurt)",
    "eu-west-1":      "EU (Ireland)",
    "eu-west-2":      "EU (London)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-south-1":     "Asia Pacific (Mumbai)",
}


def _http_get(url: str, timeout: float = 30.0) -> bytes:
    """GET ``url`` honouring AWS's quirky Accept-Encoding requirement.

    The b0.p.awsstatic.com pricing CDN returns 404 unless the request carries
    ``Accept-Encoding: gzip, deflate, br``. Handles gzip decoding manually
    since urllib does not auto-decompress.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) bedrock-audit/1.0",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return raw


def _fetch_pricing_id_map(region: str) -> dict[str, float]:
    """Return ``{placeholder_id: price}`` for the target region.

    Merges both pricing namespaces (``bedrock`` and ``bedrockfoundationmodels``)
    into a single id→price map. The pricing-page tables use prices as-published
    (per 1M tokens for text-token rows; the scraper treats them as raw numbers
    and lets the table header tell input vs output).
    """
    display = _REGION_DISPLAY_NAMES.get(region, region)
    out: dict[str, float] = {}
    for namespace in _PRICING_NAMESPACES:
        url = f"{_PRICING_CDN_BASE}/{namespace}/USD/current/{namespace}.json"
        try:
            raw = _http_get(url)
            data = json.loads(raw)
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
            logger.warning("scrape: failed to fetch %s: %s", url, exc)
            continue
        for placeholder_id, entry in data.get("regions", {}).get(display, {}).items():
            try:
                out[placeholder_id] = float(entry["price"])
            except (KeyError, TypeError, ValueError):
                pass
    return out


_PLACEHOLDER_RE = re.compile(
    r"\{priceOf![^!]+!([A-Za-z0-9_-]+)(?:!opt)?\}"
)
_TABLE_RE = re.compile(r"&lt;table&gt;.*?&lt;/table&gt;", re.S)
_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _scrape_aws_pricing_page(
    region: str,
) -> dict[str, dict[str, float]]:
    """Return ``{model_name_lower: {input_per_1m, output_per_1m}}`` scraped
    from the AWS Bedrock pricing page.

    Skips batch / cache / flex / priority columns — only the standard
    on-demand input/output token columns are captured.
    """
    try:
        page_bytes = _http_get(_PRICING_PAGE_URL, timeout=30.0)
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("scrape: failed to fetch pricing page: %s", exc)
        return {}
    page = page_bytes.decode("utf-8", errors="replace")

    id_map = _fetch_pricing_id_map(region)
    if not id_map:
        logger.warning("scrape: pricing id map is empty; scrape will yield nothing")
        return {}

    out: dict[str, dict[str, float]] = {}
    for table_match in _TABLE_RE.finditer(page):
        try:
            table_html = html.unescape(table_match.group(0))
        except Exception:  # noqa: BLE001
            continue
        _scrape_table(table_html, id_map, out)
    return out


def _scrape_table(
    table_html: str,
    id_map: dict[str, float],
    out: dict[str, dict[str, float]],
) -> None:
    """Parse a single un-escaped <table> and merge prices into ``out``."""
    headers = [
        _TAG_RE.sub("", h).strip().lower()
        for h in _TH_RE.findall(table_html)
    ]
    if not headers:
        return

    # Locate the standard on-demand input/output token columns.
    input_col = output_col = None
    for i, h in enumerate(headers):
        is_standard = not any(
            tag in h for tag in ("batch", "cache", "flex", "priority")
        )
        if input_col is None and "input tokens" in h and is_standard:
            input_col = i
        elif output_col is None and "output tokens" in h and is_standard:
            output_col = i
    if input_col is None and output_col is None:
        return

    for tr in _TR_RE.findall(table_html):
        cells = _TD_RE.findall(tr)
        if not cells:
            continue
        name = _TAG_RE.sub("", cells[0]).strip()
        if not name or name.lower() == headers[0]:  # header repeated as tr
            continue
        record: dict[str, float] = {}
        for kind, col in (("input_per_1m", input_col), ("output_per_1m", output_col)):
            if col is None or col >= len(cells):
                continue
            ph = _PLACEHOLDER_RE.search(cells[col])
            if not ph:
                continue
            price = id_map.get(ph.group(1))
            if price is not None:
                record[kind] = price
        if record:
            # First-wins per (model_name, column). The AWS pricing page repeats
            # each model across several tables (standard / extended access /
            # batch / batch+extended). The standard on-demand table comes
            # first in document order, so taking the first non-null price per
            # column gives the canonical rate.
            existing = out.setdefault(name.lower(), {})
            for k, v in record.items():
                existing.setdefault(k, v)


def _lookup_via_scrape(
    entry: dict[str, Any],
    scrape_map: dict[str, dict[str, float]],
) -> dict[str, float] | None:
    """Look an entry up in the scraped pricing-page map.

    Tries the modelName / inferenceProfileName first, then a substring fallback.
    """
    if not scrape_map:
        return None
    candidates: list[str] = []
    for f in ("modelName", "inferenceProfileName"):
        n = (entry.get(f) or "").strip().lower()
        if n:
            candidates.append(n)
    # Also try a normalised form of the model ID (strip cross-region prefix)
    mid = _entry_id(entry).lower()
    for prefix in ("us.", "eu.", "apac.", "global."):
        if mid.startswith(prefix):
            mid = mid[len(prefix):]
            break
    if mid:
        # The page uses friendly names ("Claude Sonnet 4.6") so id matches are
        # rare — keep this as a last-ditch substring check.
        candidates.append(mid)

    for cand in candidates:
        if cand in scrape_map:
            return scrape_map[cand]
    for cand in candidates:
        for key, value in scrape_map.items():
            if cand and (cand in key or key in cand):
                return value
    return None


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


def _lookup_via_alias(
    entry: dict[str, Any],
    pricing_map: dict[str, dict[str, float]],
) -> dict[str, float] | None:
    """Try the hardcoded alias map by entry id, optionally stripping the
    cross-region prefix so inference profiles inherit their underlying
    foundation model's alias."""
    mid = _entry_id(entry).lower()
    candidates = [mid]
    for prefix in ("us.", "eu.", "apac.", "global."):
        if mid.startswith(prefix):
            candidates.append(mid[len(prefix):])
    for cand in candidates:
        target = _PRICING_NAME_ALIASES.get(cand)
        if target and target.lower() in pricing_map:
            return pricing_map[target.lower()]
    return None


def _lookup_via_profile_fallback(
    entry: dict[str, Any],
    pricing_map: dict[str, dict[str, float]],
    foundation_pricing_by_id: dict[str, dict[str, float]],
) -> dict[str, float] | None:
    """For an inference profile, walk entry.models[].modelArn and look up the
    underlying foundation model's pricing.

    Cross-region inference profiles bill at the underlying model's rate but
    don't get their own Pricing API SKU. ``foundation_pricing_by_id`` is the
    {foundation_model_id_lower: pricing_dict} map built once at the start of
    the run so this lookup is O(1)."""
    if _entry_kind(entry) != "inference-profile":
        return None
    for m in entry.get("models") or []:
        arn = (m.get("modelArn") or "").lower()
        if not arn:
            continue
        fm_id = arn.split("/")[-1]
        if fm_id in foundation_pricing_by_id:
            return foundation_pricing_by_id[fm_id]
    return None


def _attach_pricing(
    entry: dict[str, Any],
    pricing_map: dict[str, dict[str, float]],
    foundation_pricing_by_id: dict[str, dict[str, float]],
    scrape_map: dict[str, dict[str, float]],
    global_pricing_error: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Return (pricing_dict, pricingProbeError).

    Resolution order:
      1. Direct candidate match (modelName, derived keys).
      2. Hardcoded alias map (``_PRICING_NAME_ALIASES``).
      3. Substring fuzzy match against the pricing map keys.
      4. Inference-profile foundation-model fallback.
      5. AWS Bedrock pricing-page scrape (when ``--scrape`` was passed).

    ``pricing_dict.source`` records which path won. ``pricingProbeError`` is:
      - the global Pricing API error if the upstream fetch failed
      - "NotFoundInPricingAPI" if every lookup path failed
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

    chosen: dict[str, float] | None = None
    source = "aws-pricing-api"

    # 1. Direct candidate match
    candidates = _build_pricing_candidates(entry)
    for cand in candidates:
        if cand in pricing_map:
            chosen = pricing_map[cand]
            break

    # 2. Alias map
    if chosen is None:
        aliased = _lookup_via_alias(entry, pricing_map)
        if aliased is not None:
            chosen = aliased
            source = "aws-pricing-api+alias"

    # 3. Substring fuzzy match (legacy behaviour, kept as last-resort)
    if chosen is None:
        for key, value in pricing_map.items():
            if any(cand and (cand in key or key in cand) for cand in candidates):
                chosen = value
                break

    # 4. Inference-profile foundation-model fallback
    if chosen is None:
        fallback = _lookup_via_profile_fallback(
            entry, pricing_map, foundation_pricing_by_id
        )
        if fallback is not None:
            chosen = fallback
            source = "aws-pricing-api+profile-fallback"

    # 5. Pricing-page scrape (only populated when --scrape was passed)
    if chosen is None:
        scraped = _lookup_via_scrape(entry, scrape_map)
        if scraped is not None:
            chosen = scraped
            source = "aws-bedrock-pricing-page"

    pricing = {
        "input_per_1m": (chosen or {}).get("input_per_1m"),
        "output_per_1m": (chosen or {}).get("output_per_1m"),
        "currency": "USD",
        "source": source,
    }
    error = None if chosen is not None else "NotFoundInPricingAPI"
    return pricing, error


def _build_foundation_pricing_by_id(
    foundation_models: list[dict[str, Any]],
    pricing_map: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Build {foundation_model_id_lower: pricing_dict} for the profile fallback.

    Pre-resolves each foundation model's pricing once so the per-profile
    fallback in _lookup_via_profile_fallback runs in O(1).
    """
    out: dict[str, dict[str, float]] = {}
    for fm in foundation_models:
        mid = (fm.get("modelId") or "").lower()
        if not mid:
            continue
        # Reuse the same resolution path: direct candidate match + alias.
        candidates = _build_pricing_candidates(fm)
        for cand in candidates:
            if cand in pricing_map:
                out[mid] = pricing_map[cand]
                break
        if mid in out:
            continue
        aliased = _lookup_via_alias(fm, pricing_map)
        if aliased is not None:
            out[mid] = aliased
    return out


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
        "--scrape",
        action="store_true",
        help=(
            "Scrape https://aws.amazon.com/bedrock/pricing/ as a fifth-tier "
            "pricing lookup. Recovers prices for models AWS Pricing API does "
            "not carry (most Claude 4.x, Palmyra X4/X5, etc)."
        ),
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

    scrape_map: dict[str, dict[str, float]] = {}
    if args.scrape:
        print("Scraping AWS Bedrock pricing page...", file=sys.stderr)
        scrape_map = _scrape_aws_pricing_page(args.region)
        print(
            f"  Recovered {len(scrape_map)} model name → price entries from page.",
            file=sys.stderr,
        )

    print(
        f"Probing {len(entries)} entries (concurrency={args.concurrency})...",
        file=sys.stderr,
    )
    probe_results = asyncio.run(_probe_all(entries, args.region, args.concurrency))

    canonical_providers = _build_canonical_provider_map(foundation)
    foundation_pricing_by_id = _build_foundation_pricing_by_id(
        foundation, pricing_map
    )

    available: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    n_tool = n_priced = n_access_denied = 0
    for entry, (tool_supported, tool_probe_error) in zip(
        entries, probe_results, strict=True
    ):
        record = dict(entry)
        record["entryKind"] = _entry_kind(entry)
        record["providerName"] = _provider_of(entry, canonical_providers)
        record["pricingKind"] = _classify_pricing_kind(entry)
        record["toolCallingSupported"] = tool_supported
        record["toolProbeError"] = tool_probe_error
        pricing, pricing_probe_error = _attach_pricing(
            entry,
            pricing_map,
            foundation_pricing_by_id,
            scrape_map,
            pricing_global_error,
        )
        record["pricing"] = pricing
        record["pricingProbeError"] = pricing_probe_error

        if tool_supported is True:
            n_tool += 1
        if pricing["input_per_1m"] is not None or pricing["output_per_1m"] is not None:
            n_priced += 1
        if tool_probe_error == "AccessDenied":
            n_access_denied += 1
            unavailable.append(record)
        else:
            available.append(record)

    # Sort: priced records first (by provider, id), then unpriced (by provider,
    # id). "Priced" = at least one of input/output_per_1m is non-null.
    def _sort_key(r: dict[str, Any]) -> tuple[int, str, str]:
        p = r.get("pricing") or {}
        unpriced = 1 if (p.get("input_per_1m") is None and p.get("output_per_1m") is None) else 0
        return (unpriced, r.get("providerName") or "", _entry_id(r))

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
