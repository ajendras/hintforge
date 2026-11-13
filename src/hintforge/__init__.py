"""HintForge — AI-powered contextual password recovery.

Local LLM driven password candidate generation and testing
for encrypted ZIP, RAR, PDF, 7z and TAR archives.
"""

from __future__ import annotations

from .models import Candidate
from .oracle import generate_candidates
from .core import recover, analyze
from .strategies import run_strategy

__version__ = "0.1.0"
__all__ = [
    "recover",
    "analyze",
    "generate_candidates",
    "run_strategy",
    "Candidate",
]

__author__ = "HintForge Collective"
__license__ = "MIT"
