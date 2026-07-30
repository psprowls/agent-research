"""Subagent adapters: per-subagent input gathering behind a uniform protocol."""

from __future__ import annotations

from .guidance_classifier import GuidanceClassifierAdapter
from .guidance_orchestrator import GuidanceOrchestratorAdapter
from .librarian import LibrarianAdapter
from .prose_refresher import ProseRefresherAdapter
from .query_orchestrator import QueryOrchestratorLoopAdapter
from .synthesizer import SynthesizerAdapter

# name → zero-arg constructor (synthesizer accepts an optional excerpts_path).
ADAPTERS = {
    "guidance_classifier": GuidanceClassifierAdapter,
    "prose_refresher": ProseRefresherAdapter,
    "guidance_orchestrator": GuidanceOrchestratorAdapter,
    "librarian": LibrarianAdapter,
    "synthesizer": SynthesizerAdapter,
}

# name → constructor for tool-loop adapters (real agentic loops). Kept separate
# from ADAPTERS so the single-shot path stays untouched.
LOOP_ADAPTERS = {
    "query_orchestrator": QueryOrchestratorLoopAdapter,
}
