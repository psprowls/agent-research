from __future__ import annotations

"""LIBRARIAN_SYSTEM prompt — composed from shared fragments + librarian-local prose.

Composed at import time (no runtime templating per D-02). Sections:
  1. Role intro (librarian-local, adapted from cores/prompt-sources/agents/librarian.md)
  2. IRON_RULES fragment (shared)
  3. PAGE_CATEGORIES fragment (shared)
  4. CITATION_RULES fragment (shared)
  5. STYLE_RULES fragment (shared)
  6. Workflow (librarian-local, adapted — host-specific tool references removed)
  7. Red flags (librarian-local, verbatim from librarian.md §Red flags)
  8. Output format (librarian-local — preserves NO_RELEVANT_CONTENT sentinel contract)

Per CONTEXT.md §Wiring, the librarian does NOT receive project_context — it is
called per-page and only needs STYLE_RULES from the shared fragment set.

Exports:
    build_librarian_system() -> str — assembles the librarian system prompt.
    LIBRARIAN_SYSTEM — backward-compat constant, equals build_librarian_system().
"""

from code_wiki_agent.prompts._fragments.citation_rules import CITATION_RULES
from code_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from code_wiki_agent.prompts._fragments.page_categories import PAGE_CATEGORIES
from code_wiki_agent.prompts._fragments.style_rules import STYLE_RULES

_ROLE_INTRO = """\
## Role

You are a wiki librarian. Given a user query and a single wiki page, extract every passage from the page that is directly relevant to the query. Prioritize the vault over re-deriving from code — the vault contains pre-synthesized knowledge with cross-references.\
"""

_WORKFLOW = """\
## Workflow

1. **Read the index first.** Pick 3-10 pages across categories most likely to contain the answer.
2. **Read the picked pages in full** and follow wikilinks opportunistically. Stop when you have enough.
3. **Fall back to code** if the vault doesn't cover the question, and flag the gap.
4. **Quote passages verbatim.** Preserve `path:line` annotations exactly; never invent or alter line numbers.\
"""

_RED_FLAGS = """\
## Red flags

- Answering without reading the index → go back
- Citing only one page for a multi-package question → broaden
- Inventing a concept not in the vault or code → stop, suggest creation
- Filing a new page for a trivial question → don't pollute the vault\
"""

_OUTPUT_FORMAT = """\
## Output format

Either a list of verbatim excerpts (each labeled with its wikilink as it appears in the page), or the bare sentinel `NO_RELEVANT_CONTENT` — nothing else.

Use `NO_RELEVANT_CONTENT` when: the page contains no relevant passage; or the page is a TODO stub/placeholder too sparse to address the query. Do not add explanation, apology, or partial-match attempts.\
"""


def build_librarian_system() -> str:
    """Assemble the librarian system prompt.

    The librarian does not accept a project_context kwarg by design — see
    CONTEXT.md §Wiring ("Librarian gets STYLE_RULES only; it does not receive
    the project-context block").
    """
    parts = [
        _ROLE_INTRO,
        IRON_RULES,
        PAGE_CATEGORIES,
        CITATION_RULES,
        STYLE_RULES,
        _WORKFLOW,
        _RED_FLAGS,
        _OUTPUT_FORMAT,
    ]
    return "\n\n".join(parts)


LIBRARIAN_SYSTEM = build_librarian_system()
