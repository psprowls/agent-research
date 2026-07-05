"""Root conftest, loaded for both whole-suite and --package-scoped test runs.

A shell-exported FORCE_COLOR forces rich/click to emit ANSI escapes even when
output isn't a tty, which breaks CLI help-text and no-color-mode assertions
that check for literal substrings. Tests should be deterministic regardless
of the invoking shell's environment.
"""

from __future__ import annotations

import os

os.environ.pop("FORCE_COLOR", None)
