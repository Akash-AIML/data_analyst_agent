"""Ensure the repo root is importable so ``agents`` resolves in tests."""

import os
import sys

ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
