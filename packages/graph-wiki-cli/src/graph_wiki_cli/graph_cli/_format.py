"""Re-export shim — formatting logic lives in graph_io.render, reached via
graph_wiki_core.commands.graph_query (graph-wiki-cli may not import graph_io
directly — see 2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core).

This module is preserved (not deleted) because 4 existing cli modules import
from it: q_imported_by, q_exported_by, q_callers, q_callees. (q_find was
migrated to import graph_io.render directly in Phase 59; q_exports and q_imports
were removed in 2026-06-16 when the imports/exports commands folded into
describe path.) Deleting it would break those callers.

New code should import from graph_wiki_core.commands.graph_query directly.
"""

from graph_wiki_core.commands.graph_query import (  # noqa: F401
    _importer_human,
    _importer_json,
    _is_importer_batch,
    _to_dict,
)
from graph_wiki_core.commands.graph_query import render as _render_module

# graph_query.render is the graph_io.render *module* (needed by describe_*
# callers doing `_render.format_repo(...)`); this shim's own callers
# (q_callers/q_callees/q_imported_by/q_exported_by) call `_format.render(...)`
# directly as a function, so bind this module's `render` name to the
# module's own `render` function attribute (graph_io.render.render).
render = _render_module.render
