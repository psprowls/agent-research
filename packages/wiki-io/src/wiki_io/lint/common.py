"""Shared helpers for lint check groups: frontmatter parsing, table parsing,
regex constants used across modules.
"""

from __future__ import annotations

import re

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Wikilinks: ``[[target]]``, ``[[target#anchor]]``, ``[[target|alias]]``.
# Inside markdown table cells the alias separator is escaped as ``\|`` so it
# doesn't collide with the cell delimiter — the lookahead ``(?!\\\|)`` stops
# the target at that escaped pipe so the alias group can consume ``\|alias``.
WIKILINK_RE = re.compile(r"\[\[((?:(?!\\\|)[^\]|#])+)(?:#[^\]|]*)?(?:\\?\|[^\]]*)?\]\]")
LOG_ENTRY_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\]", re.MULTILINE)

# A "## File map - <name>" section runs from its heading to the next H2 or EOF.
# Group 1: the package/app name from the heading. Group 2: the section body
# (which contains H3-H6 sub-section headers and bullet lists).
FILE_MAP_SECTION_RE = re.compile(
    r"^##\s+File map - (\S.*?)\s*\n(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
# Sub-section header inside a File map block. Levels 3-6 (### through ######)
# correspond to directory depths 1-4 below the package root. The captured
# group is the full path from the heading (e.g. ``<pkg>/<a>/``).
SECTION_HEADER_RE = re.compile(r"^#{3,6}\s+(\S.+?)\s*$", re.MULTILINE)
# Strip fenced code blocks (```...```) and inline code (`...`) before scanning
# for wikilinks — bracketed content inside code is content, not a link.
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def indented_code_spans(text: str) -> list[tuple[int, int]]:
    """Return spans of CommonMark indented code blocks in ``text``.

    An indented code block is a run of one or more consecutive lines starting
    with at least 4 spaces or one tab, preceded by a blank line or the start
    of the document. The run ends at the first non-indented non-blank line
    (or EOF).

    Returns a list of ``(start_byte, end_byte)`` half-open spans, sorted
    ascending, non-overlapping. Empty input or text with no indented blocks
    returns ``[]``.

    Per CommonMark §4.4; used by ``wiki_io.link_rewriter.rewrite_text`` to
    mask indented code regions from wikilink rewriting. The helper does NOT
    look at fences — the caller is expected to union with fenced/inline
    spans separately (double-coverage is harmless).
    """
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    # Tokenize into lines, recording absolute byte positions.
    lines: list[tuple[int, int, str]] = []  # (start, end, line_text)
    cursor = 0
    for line in text.splitlines(keepends=True):
        lines.append((cursor, cursor + len(line), line))
        cursor += len(line)

    def is_blank(s: str) -> bool:
        return s.strip() == ""

    def is_indented(s: str) -> bool:
        if s.startswith("\t"):
            return True
        if is_blank(s):
            return False
        return s.startswith("    ")

    i = 0
    n = len(lines)
    while i < n:
        start, end, ln = lines[i]
        prev_blank_or_start = (i == 0) or is_blank(lines[i - 1][2])
        if prev_blank_or_start and is_indented(ln):
            block_start = start
            block_end = end
            j = i + 1
            while j < n and is_indented(lines[j][2]):
                block_end = lines[j][1]
                j += 1
            spans.append((block_start, block_end))
            i = j
            continue
        i += 1
    return spans


def _is_placeholder_target(target: str) -> bool:
    """Check if a wikilink target is a placeholder/template token.

    Placeholder targets contain template tokens like ..., <name>, etc.
    and should not be treated as broken links.

    Relocated from the upstream lint_wiki module so the predicate sits next
    to WIKILINK_RE in the shared lint helpers module.

    Args:
        target: The wikilink target string (e.g., "wiki/packages/...")

    Returns:
        True if target contains placeholder markers (..., <, or >), False otherwise.
    """
    return "..." in target or "<" in target or ">" in target


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def strip_code(text: str) -> str:
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter block (---…---) from text.

    If no frontmatter block is found, returns text unchanged.
    Otherwise returns only the body after the closing ---.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    return text[m.end() :]


def expand_braces(name: str) -> list[str]:
    """Expand a single brace group like ``{a,b,c}.ts`` into multiple names.

    Only the first brace group is expanded (one level, no nesting). Returns
    ``[name]`` when no braces are present.
    """
    m = re.search(r"\{([^{}]+)\}", name)
    if not m:
        return [name]
    prefix = name[: m.start()]
    suffix = name[m.end() :]
    options = [o.strip() for o in m.group(1).split(",") if o.strip()]
    return [prefix + opt + suffix for opt in options]


def parse_inline_list(value: str) -> list[str]:
    """Parse a YAML inline list like ``[a, b, "c d"]`` into a list of strings.

    Returns ``[]`` for empty or non-list values. Whitespace and surrounding
    quotes are stripped from each item.
    """
    s = (value or "").strip()
    if not s.startswith("["):
        return []
    s = s.strip("[]").strip()
    if not s:
        return []
    out: list[str] = []
    for item in s.split(","):
        item = item.strip().strip("'\"")
        if item:
            out.append(item)
    return out


def find_section(text: str, heading: str) -> str | None:
    """Return the body of a ``## <heading>`` section (no heading line),
    stopping at the next ``##`` or end of file. None if not found.
    """
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1)


def parse_markdown_table(body: str) -> tuple[list[str], list[list[str]]] | None:
    """Parse the first markdown table in ``body``.

    Returns ``(headers, rows)`` or ``None`` if no recognizable table is found.
    Pipes inside cells should be escaped as ``\\|`` (preserved verbatim in
    the parsed cell).
    """
    lines = [ln.rstrip() for ln in body.splitlines()]
    headers: list[str] | None = None
    rows: list[list[str]] = []
    in_table = False
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            if in_table:
                break
            continue
        cells = _split_pipes(s)
        if headers is None:
            headers = cells
            continue
        # Separator row like |---|---|
        if all(set(c.strip()) <= set("-: ") for c in cells) and any("-" in c for c in cells):
            in_table = True
            continue
        if in_table:
            rows.append(cells)
    if headers is None:
        return None
    return headers, rows


def _split_pipes(line: str) -> list[str]:
    """Split a markdown-table row on ``|``, honoring ``\\|`` escapes.

    Strips the leading and trailing ``|`` (with surrounding whitespace).
    Returns the trimmed cell contents.
    """
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if buf:
        cells.append("".join(buf).strip())
    # Drop the empty cells produced by the leading/trailing ``|``.
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def parse_section_entries(body: str, pkg_name: str) -> list[tuple[str, bool]]:
    """Parse a ``## File map - <pkg>`` body into ``(internal_path, is_dir)`` tuples.

    Internal paths are relative to the package root — the ``<pkg>/`` prefix
    on section headers is stripped before being used as the path context.

    **New table format (post-2026-05):**

    Each H3 section (``### <pkg>/<sub>/``) sets the active path context and
    is recorded as a directory entry. Within a section, the first markdown
    table is parsed for rows: ``Path | Kind | Description``. The Path cell
    is expressed relative to the section's root. ``Kind`` is ``file`` or
    ``dir``; a trailing ``/`` on the Path cell (or ``Kind == dir``) marks
    directory entries. Brace expansion is applied to file paths only.

    **Graceful fallback for old heading+bullet format (pre-2026-05):**

    When the section body contains no markdown table, the function still
    returns whatever directory entries it accumulated from H3 section
    headers (e.g. ``("src", True)``). File-row entries are absent.
    This means the drift lint may still flag legitimately-missing
    directories on old-format pages (a true positive), but it will not
    crash and will not emit false positives for phantom bullet entries.
    Pages migrate organically when the next scan detects the unfilled
    template condition and re-emits the block in the new table format.

    Brace-expanded names like ``{a,b,c}.ts`` produce one file entry each.
    Brace expansion is not applied to directory rows.
    """
    entries: list[tuple[str, bool]] = []
    seen_dirs: set[str] = set()
    current_path = ""

    lines = body.splitlines()
    n = len(lines)
    i = 0

    # Regex to strip backticks from a path cell
    _BACKTICK_RE = re.compile(r"^\s*`(.+?)`\s*$")

    while i < n:
        line = lines[i]
        m = SECTION_HEADER_RE.match(line)
        if m:
            header_text = m.group(1).rstrip("/").strip()
            if header_text == pkg_name:
                current_path = ""
            elif header_text.startswith(pkg_name + "/"):
                current_path = header_text[len(pkg_name) + 1:]
            else:
                current_path = ""
            if current_path and current_path not in seen_dirs:
                entries.append((current_path, True))
                seen_dirs.add(current_path)
            i += 1

            # Collect the section block: all lines until the next H3+ header or end
            section_lines: list[str] = []
            while i < n and not SECTION_HEADER_RE.match(lines[i]):
                section_lines.append(lines[i])
                i += 1

            # Parse the first markdown table in this section block
            table_result = parse_markdown_table("\n".join(section_lines))
            if table_result is None:
                # No table found — graceful fallback, keep directory entry only
                continue

            _headers, rows = table_result
            for row in rows:
                if len(row) < 2:
                    continue
                raw_path = row[0]
                raw_kind = row[1].strip().lower() if len(row) > 1 else ""

                # Strip backticks from path cell
                bm = _BACKTICK_RE.match(raw_path)
                token = bm.group(1) if bm else raw_path.strip()

                is_dir = token.endswith("/") or raw_kind == "dir"
                name = token.rstrip("/")
                if not name:
                    continue

                if is_dir:
                    full_path = f"{current_path}/{name}" if current_path else name
                    if full_path not in seen_dirs:
                        seen_dirs.add(full_path)
                        entries.append((full_path, True))
                else:
                    # File entry — apply brace expansion
                    for expanded in expand_braces(name):
                        full_path = f"{current_path}/{expanded}" if current_path else expanded
                        entries.append((full_path, False))
        else:
            i += 1

    return entries
