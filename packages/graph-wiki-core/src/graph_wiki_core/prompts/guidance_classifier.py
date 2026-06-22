"""Per-file guidance classifier prompt + fail-safe closed-vocab parser.

The model sees one file's bounded context (path + head + symbol names) and a
closed vocabulary (topic list + tag allowlist), and returns the applicable
subset. Anything off-vocab is dropped on parse and never written to the index.
"""

from __future__ import annotations

import re

import yaml
from guidance_io.vocab import Vocab, canonical_tag

GUIDANCE_CLASSIFIER_SYSTEM = """You classify a single source file into a CLOSED \
vocabulary of guidance topics and tags, so that prescriptive guidance pages can \
later be matched to the file.

Rules:
- Choose ONLY from the provided topic list and tag allowlist. Never invent values.
- Return the APPLICABLE SUBSET — often one topic and zero to three tags. Empty is fine.
- A topic describes the technology/domain the file is about (e.g. the language or framework).
- Tags are coarse, cross-cutting concerns the file clearly exercises.

Output ONLY a YAML mapping, no prose and no code fences:
topics: [<subset of the topic list>]
tags: [<subset of the tag allowlist>]"""

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


def build_guidance_classifier_prompt(
    rel_path: str,
    head: str,
    symbols: list[str],
    topics: list[str],
    tags: list[str],
) -> tuple[str, str]:
    """Return ``(system, human)`` for classifying one file."""
    symbol_line = ", ".join(symbols[:60]) if symbols else "(none resolved)"
    human = "\n".join(
        [
            f"File: {rel_path}",
            "",
            f"Symbols defined in this file: {symbol_line}",
            "",
            "File head:",
            head.strip()[:2000],
            "",
            f"Topic list (choose a subset): {', '.join(topics)}",
            f"Tag allowlist (choose a subset): {', '.join(tags)}",
            "",
            "Classify this file. Output the YAML mapping only.",
        ]
    )
    return GUIDANCE_CLASSIFIER_SYSTEM, human


def parse_classifier_response(text: str, vocab: Vocab) -> dict:
    """Parse the YAML reply; keep only in-vocab topics/tags. Fail-safe to empties."""
    raw = _FENCE_RE.sub("", (text or "").strip())
    try:
        obj = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {"topics": [], "tags": []}
    if not isinstance(obj, dict):
        return {"topics": [], "tags": []}

    topics = [t for t in (obj.get("topics") or []) if str(t) in vocab.topics]
    tags: list[str] = []
    for t in obj.get("tags") or []:
        canon = canonical_tag(str(t), vocab)
        if canon is not None and canon not in tags:
            tags.append(canon)
    # de-dup topics preserving order
    seen: set[str] = set()
    topics = [t for t in (str(x) for x in topics) if not (t in seen or seen.add(t))]
    return {"topics": topics, "tags": tags}
