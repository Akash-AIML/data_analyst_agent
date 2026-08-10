"""Ensure the repo root is importable so ``agents`` resolves in tests."""

import os
import sys

# Safeguard against broken PyTorch/transformers DLL initialization on Windows
try:
    import transformers  # noqa: F401
except OSError:
    sys.modules["transformers"] = None
except ImportError:
    pass

ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
