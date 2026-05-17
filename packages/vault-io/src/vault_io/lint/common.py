"""Shared helpers for lint check groups: frontmatter parsing, table parsing,
regex constants used across modules.
"""

from __future__ import annotations

import re

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
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
# A bullet item: ``- `<token>` — description``. Trailing slash on the token
# marks a directory entry; the description is ignored.
# Group 1: leading indent (space count → nesting depth).
# Group 2: the bullet token; trailing slash marks a directory entry.
BULLET_RE = re.compile(r"^( *)-\s+`([^`]+)`")

# Strip fenced code blocks (```...```) and inline code (`...`) before scanning
# for wikilinks — bracketed content inside code is content, not a link.
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


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

    Walks the body line by line:

    - H3-H6 headers (``### <pkg>/<a>/``, ``#### <pkg>/<a>/<b>/``, ...) set
      the active path context and are themselves recorded as directory
      entries. A header also resets the bullet indentation stack.
    - Bullets (``- `<token>` — ...``) are recorded as files (no trailing
      slash) or directories (trailing slash). Bullets nested under a
      directory bullet (greater leading indent) resolve under that
      directory; the parser maintains a stack of in-scope directory
      bullets and pops entries whose indent is greater than or equal to
      the current bullet's indent.
    - Bullets at the section's top indent (with no header and no enclosing
      directory bullet) sit at the package root.

    Brace-expanded names like ``{a,b,c}.ts`` produce one file entry each.
    Brace expansion is not applied to directory bullets.
    """
    entries: list[tuple[str, bool]] = []
    seen_dirs: set[str] = set()
    current_path = ""
    # Stack of (indent, dir_name) for directory bullets currently in scope.
    # Reset every time an H3-H6 header matches.
    dir_stack: list[tuple[int, str]] = []

    for line in body.splitlines():
        m = SECTION_HEADER_RE.match(line)
        if m:
            header_text = m.group(1).rstrip("/").strip()
            if header_text == pkg_name:
                current_path = ""
            elif header_text.startswith(pkg_name + "/"):
                current_path = header_text[len(pkg_name) + 1 :]
            else:
                current_path = ""
            if current_path and current_path not in seen_dirs:
                entries.append((current_path, True))
                seen_dirs.add(current_path)

            dir_stack = []
            continue

        bm = BULLET_RE.match(line)
        if not bm:
            continue

        indent = len(bm.group(1))
        token = bm.group(2)
        is_dir = token.endswith("/")
        name = token.rstrip("/")
        if not name:
            continue

        # Pop any directory bullets at the same or deeper indent than this
        # bullet — they no longer enclose us.
        while dir_stack and dir_stack[-1][0] >= indent:
            dir_stack.pop()

        prefix_parts: list[str] = []
        if current_path:
            prefix_parts.append(current_path)
        prefix_parts.extend(d for _, d in dir_stack)
        prefix = "/".join(prefix_parts)

        for n in expand_braces(name):
            full_path = f"{prefix}/{n}" if prefix else n
            if is_dir:
                if full_path in seen_dirs:
                    continue
                seen_dirs.add(full_path)
            entries.append((full_path, is_dir))

        # Push this directory onto the stack so deeper-indented bullets
        # resolve under it. Brace expansion only affects file leaves; for
        # directory bullets we push the unexpanded name (file maps don't
        # use brace expansion in dir tokens).
        if is_dir:
            dir_stack.append((indent, name))
    return entries
