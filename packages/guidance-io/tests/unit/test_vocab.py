from __future__ import annotations

from pathlib import Path

import yaml
from guidance_io.vocab import (
    Vocab,
    canonical_tag,
    load_vocab,
    seed_tags,
    write_tags_yaml,
)


def _page(ws: Path, topic: str, slug: str, fm: dict) -> None:
    d = ws / "wiki" / "guidance" / topic
    d.mkdir(parents=True, exist_ok=True)
    body = "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Guidance\nx\n"
    (d / f"{slug}.md").write_text(body, encoding="utf-8")


def test_load_vocab_topics_from_folders(tmp_path: Path) -> None:
    _page(tmp_path, "python", "a", {"title": "A", "tags": ["retry"]})
    _page(tmp_path, "langchain", "b", {"title": "B", "tags": ["middleware"]})
    vocab = load_vocab(tmp_path)
    assert vocab.topics == frozenset({"python", "langchain"})


def test_load_vocab_tags_mapping_form(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "guidance").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(
        yaml.safe_dump({"tags": ["retry", "styling"], "aliases": {"retries": "retry"}}),
        encoding="utf-8",
    )
    vocab = load_vocab(tmp_path)
    assert vocab.tags == frozenset({"retry", "styling"})
    assert vocab.aliases == {"retries": "retry"}


def test_load_vocab_tags_list_form(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "guidance").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["retry", "styling"]), encoding="utf-8")
    vocab = load_vocab(tmp_path)
    assert vocab.tags == frozenset({"retry", "styling"})
    assert vocab.aliases == {}


def test_load_vocab_missing_tags_yaml(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "guidance" / "python").mkdir(parents=True)
    vocab = load_vocab(tmp_path)
    assert vocab.tags == frozenset()
    assert vocab.aliases == {}
    assert vocab.vocab_hash  # non-empty


def test_canonical_tag_alias_and_kebab(tmp_path: Path) -> None:
    vocab = Vocab(
        topics=frozenset({"python"}),
        tags=frozenset({"retry", "styling"}),
        aliases={"retries": "retry"},
        vocab_hash="h",
    )
    assert canonical_tag("Retries", vocab) == "retry"
    assert canonical_tag("Styling", vocab) == "styling"
    assert canonical_tag("nonsense", vocab) is None


def test_vocab_hash_stable_and_order_independent(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "guidance" / "python").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "uv").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["b", "a"]), encoding="utf-8")
    h1 = load_vocab(tmp_path).vocab_hash
    h2 = load_vocab(tmp_path).vocab_hash
    assert h1 == h2
    # changing a tag changes the hash
    (tmp_path / "wiki" / "guidance" / "tags.yaml").write_text(yaml.safe_dump(["a", "b", "c"]), encoding="utf-8")
    assert load_vocab(tmp_path).vocab_hash != h1


def test_seed_tags_unions_page_tags(tmp_path: Path) -> None:
    _page(tmp_path, "python", "a", {"title": "A", "tags": ["Retry", "io"]})
    _page(tmp_path, "uv", "b", {"title": "B", "tags": ["io", "Locking"]})
    assert seed_tags(tmp_path) == ["io", "locking", "retry"]


def test_write_tags_yaml_roundtrips(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "guidance").mkdir(parents=True)
    path = write_tags_yaml(tmp_path, ["retry", "io"])
    assert path.exists()
    loaded = yaml.safe_load(path.read_text())
    assert loaded == {"tags": ["retry", "io"]}
