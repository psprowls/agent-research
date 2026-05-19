#!/usr/bin/env python3
"""Plugin shim for detect_containers — delegates to vault_io.detect_containers."""
import sys

from vault_io.detect_containers import main

if __name__ == "__main__":
    main()
