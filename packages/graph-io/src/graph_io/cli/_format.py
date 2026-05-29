"""Re-export shim — formatting logic lives in graph_io.render.

This module is preserved (not deleted) because 7 existing cli modules import
from it: q_find, q_imported_by, q_exported_by, q_exports, q_imports,
q_callers, q_callees. Deleting it would break those callers.

New code should import from graph_io.render directly.
"""

from graph_io.render import (  # noqa: F401
    _importer_human,
    _importer_json,
    _is_importer_batch,
    _to_dict,
    render,
)
