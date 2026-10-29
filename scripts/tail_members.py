#!/usr/bin/env python3
"""Convenience CLI entry point for tailing Fitness First home studio member activity.

Usage:
    python scripts/tail_members.py [-i INTERVAL] [--reset] [--once] [--json]
"""

from __future__ import annotations

import os
import sys

# Ensure repository root / src is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fitness_first_germany_mcp.tail import main

if __name__ == "__main__":
    main()

