"""Pydantic models for HintForge.

Core data classes used across the CLI, oracle, core orchestrator and strategies.
All models include input validation and helpful error messages.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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

    def __str__(self) -> str:
        return f"{self.value} (score={self.score:.3f})"


class Config(BaseModel):
    """Global configuration for HintForge.

    Loaded from config.toml (or defaults). Controls model selection,
    candidate limits, enabled strategies and dictionary paths.
    """

    model: str = Field(
        default="llama3",
        description="Ollama model name (must be available locally).",
    )
    max_candidates: int = Field(
        default=75,
        ge=1,
        le=500,
        description="Maximum number of candidates to generate and test.",
    )
    temperature: float = Field(
        default=0.75,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation.",
    )
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    enabled_strategies: list[str] = Field(
        default_factory=lambda: ["ai", "dictionary", "mask"],
        description="Strategies to run in hybrid mode.",
    )
    dictionary_path: str | None = Field(
        default=None,
        description="Path to optional custom wordlist (one password per line).",
    )
    min_score_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Discard candidates below this score.",
    )
    dry_run: bool = False

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SessionState(BaseModel):
    """Serializable recovery session for checkpoint/resume functionality.

    Persisted as JSON in .hintforge/ directory.
    """

    archive_path: str
    hint: str
    candidates_tested: int = Field(default=0, ge=0)
    total_candidates: int = Field(default=75, ge=1)
    tested: set[str] = Field(default_factory=set)
    found: str | None = None
    start_time: float = Field(default=0.0)
    end_time: float | None = None
    candidates: list[Candidate] | None = None
    strategy_stats: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        json_encoders={set: list},
    )

    def mark_tested(self, password: str) -> None:
        """Record a tested password (idempotent)."""
        self.tested.add(password)
        self.candidates_tested += 1


class Job(BaseModel):
    """Represents a complete recovery job (used by future job queue)."""

    archive_path: str
    hint: str
    config: Config
    session: SessionState | None = None
    status: str = Field(default="pending", pattern="^(pending|running|done|failed)$")
    result: str | None = None
    error: str | None = None

    model_config = ConfigDict(extra="forbid")


__all__ = ["Candidate", "Config", "SessionState", "Job"]
