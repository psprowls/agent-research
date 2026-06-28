"""Frontmatter parse/emit/validate for guidance pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from guidance_io.vocab import Vocab

REQUIRED_KEYS = ("title", "category", "summary", "topic", "applies_when", "impact", "updated", "tokens")
IMPACT_VALUES = ("critical", "high", "medium", "low")
TRIGGER_LIST_KEYS = ("globs", "keywords", "entities")


def parse(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises ValueError on malformed input."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block found: text must start with ---")
    rest = text[3:]
    if "\n---" not in rest:
        raise ValueError("unclosed frontmatter block: no closing ---")
    idx = rest.index("\n---")
    fm_text = rest[:idx].strip()
    body = rest[idx + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    fm = yaml.safe_load(fm_text) if fm_text else {}
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
    return fm, body


def emit(fm: dict) -> str:
    """Serialize frontmatter dict to a fenced YAML block (--- ... ---)."""
    content = yaml.safe_dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{content}---"


def validate(fm: dict) -> list[str]:
    """Return a list of violation messages for a guidance frontmatter dict.

    Empty list means valid. Checks: required keys present, category fixed to
    'guidance', impact in the lowercased enum, topic non-empty, and (when
    present) triggers is a mapping whose globs/keywords/entities are lists.
    """
    errors: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in fm:
            errors.append(f"missing required key: {key}")

    if fm.get("category") != "guidance":
        errors.append(f"category must be 'guidance', got {fm.get('category')!r}")

    impact = fm.get("impact")
    if impact is not None and impact not in IMPACT_VALUES:
        errors.append(f"impact must be one of {IMPACT_VALUES}, got {impact!r}")

    if "topic" in fm:
        topic = fm["topic"]
        if not isinstance(topic, str) or not topic.strip():
            errors.append("topic must be a non-empty string")

    triggers = fm.get("triggers")
    if triggers is not None:
        if not isinstance(triggers, dict):
            errors.append(f"triggers must be a mapping, got {type(triggers).__name__}")
        else:
            for tk in TRIGGER_LIST_KEYS:
                if tk in triggers and not isinstance(triggers[tk], list):
                    errors.append(f"triggers.{tk} must be a list, got {type(triggers[tk]).__name__}")

    workflow = fm.get("workflow")
    if workflow is not None and not isinstance(workflow, list):
        errors.append(f"workflow must be a list of phase names, got {type(workflow).__name__}")

    role = fm.get("role")
    if role is not None and not isinstance(role, list):
        errors.append(f"role must be a list of role names, got {type(role).__name__}")

    language = fm.get("language")
    if language is not None and not isinstance(language, str):
        errors.append(f"language must be a string, got {type(language).__name__}")

    return errors


def normalize_language(fm: dict) -> None:
    """Lowercase + trim a present scalar ``language`` in place.

    No-op when ``language`` is absent or not a string. An empty/whitespace-only
    value is removed so it reads as agnostic rather than the empty string.
    """
    lang = fm.get("language")
    if isinstance(lang, str):
        norm = lang.strip().lower()
        if norm:
            fm["language"] = norm
        else:
            fm.pop("language", None)


_KEYWORD_MAX_LEN = 40


def tag_violations(fm: dict, vocab: "Vocab") -> list[str]:
    """Return one error per top-level `tags` entry not in the allowlist (post-alias)."""
    from guidance_io.vocab import canonical_tag

    errors: list[str] = []
    for tag in fm.get("tags") or []:
        if canonical_tag(str(tag), vocab) is None:
            errors.append(f"tag {tag!r} is not in the allowlist (wiki/guidance/tags.yaml)")
    return errors


def keyword_shape_warnings(fm: dict) -> list[str]:
    """Warn on triggers.keywords that look like prose, not grep-able identifiers."""
    triggers = fm.get("triggers")
    if not isinstance(triggers, dict):
        return []
    warnings: list[str] = []
    for kw in triggers.get("keywords") or []:
        s = str(kw)
        if any(c.isspace() for c in s) or len(s) > _KEYWORD_MAX_LEN:
            warnings.append(f"keyword {kw!r} looks like prose, not a grep-able identifier")
    return warnings
