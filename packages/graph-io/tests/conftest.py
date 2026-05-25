"""Add tests/ to sys.path so _git_repo helpers are importable without a package prefix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
