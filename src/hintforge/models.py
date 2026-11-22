"""Pydantic models for HintForge.

Core data classes used across the CLI, oracle, core orchestrator and strategies.
All models include input validation and helpful error messages.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Candidate(BaseModel):
    """A single password candidate with an associated likelihood score.

    Scores are normalized to [0.0, 1.0]. Higher = more likely to be correct.
    """

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Likelihood score (0.0-1.0). Higher values tested first.",
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="The candidate password string.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (source strategy, mutations, etc).",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class Config(BaseModel):
    """Global configuration for HintForge operations."""

    model: str = "llama3"
    max_candidates: int = 75
    temperature: float = 0.75
    top_p: float = 0.9
    enabled_strategies: list[str] = Field(
        default_factory=lambda: ["ai", "dictionary", "mask", "hashcat"],
        description="Strategies to run in hybrid mode.",
    )
    dictionary_path: str | None = None
    min_score_threshold: float = 0.25
    hashcat_path: str = "hashcat"
    use_gpu: bool = True
    hashcat_mask: str = "?d?d?d?d?d?d?d?d"
    online_guesses_per_second: int = 5
    cpu_guesses_per_second: int = 1_000_000
    gpu_guesses_per_second: int = 100_000_000

    model_config = ConfigDict(extra="forbid")


class SessionState(BaseModel):
    """Persistent state for a recovery session."""

    archive_path: str
    hint: str
    candidates_tested: int = 0
    total_candidates: int = 75
    tested: set[str] = Field(default_factory=set)
    found: str | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    start_time: float = 0.0
    end_time: float | None = None

    model_config = ConfigDict(extra="forbid")


class Job(BaseModel):
    """Background job model for the web dashboard."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    archive_path: str
    hint: str
    config: Config
    status: str = "pending"
    progress: float = 0.0
    result: str | None = None
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = ConfigDict(extra="forbid")


class StrengthReport(BaseModel):
    """Password strength report with entropy and crack-time projections."""

    password: str
    entropy_bits: float
    crack_times: dict[str, str]
    strength: str
    feedback: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = [
    "Candidate",
    "Config",
    "SessionState",
    "Job",
    "StrengthReport",
]
