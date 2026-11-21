"""HintForge — AI-powered contextual password recovery.

Local LLM driven password candidate generation and testing
for encrypted ZIP, RAR, PDF, 7z and TAR archives.

Automatically augments user hints with context extracted from
the archive filename, nearby files (.txt/.md content) and
EXIF/PDF metadata.

Now includes session export/import for sharing recovery state
across machines or with collaborators.
"""

from __future__ import annotations

from .models import Candidate, Job
from .oracle import generate_candidates, extract_context
from .core import (
    recover,
    analyze,
    create_job,
    get_job,
    start_job_in_background,
    export_session,
    import_session,
)
from .strategies import run_strategy
from .dashboard import run_dashboard

__version__ = "0.1.0"
__all__ = [
    "recover",
    "analyze",
    "generate_candidates",
    "extract_context",
    "run_strategy",
    "create_job",
    "get_job",
    "start_job_in_background",
    "run_dashboard",
    "export_session",
    "import_session",
    "Candidate",
    "Job",
]

__author__ = "HintForge Collective"
__license__ = "MIT"
