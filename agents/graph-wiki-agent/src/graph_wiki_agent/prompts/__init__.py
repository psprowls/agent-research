"""Prompt constants for graph-wiki-agent roles.

Shared fragment constants live under `_fragments/`; each is imported by its
consumer (per-role files or directly by command modules).  Do not eagerly
import role files here — that creates import-order coupling that breaks if any
role file is missing during incremental rollout (06-04 through 06-07).

Exports (after 06-04..06-07 land):
    LIBRARIAN_SYSTEM  -- via prompts/librarian.py
    INGESTOR_SYSTEM   -- via prompts/ingestor.py
    SCANNER_SYSTEM    -- via prompts/scanner.py
    LINTER_*_SYSTEM   -- via prompts/linter.py
    SYNTHESIZER_SYSTEM -- via prompts/synthesizer.py
    CODE_READER_SYSTEM -- via prompts/code_reader.py
"""
