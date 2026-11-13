"""Attack strategy registry and base classes for HintForge.

Provides AIStrategy, DictionaryStrategy, MaskStrategy and a hybrid runner.
Strategies are easily extensible by subclassing BaseStrategy and registering them.
Combines AI guesses with dictionary words, date masks, leetspeak mutations and
common password patterns. All candidates are scored, deduplicated and ranked.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import Candidate, Config


class BaseStrategy(ABC):
    """Abstract base class for all password generation strategies."""

    name: str = "base"

    @abstractmethod
    def run(
        self,
        hint: str | None = None,
        candidates: list[Candidate] | None = None,
        config: Config | None = None,
        **kwargs: Any,
    ) -> list[Candidate]:
        """Execute strategy and return ranked Candidate list.

        Args:
            hint: Optional user memory/hint to guide generation.
            candidates: Existing candidates to augment (for hybrid).
            config: Runtime configuration.
            **kwargs: Strategy-specific parameters.

        Returns:
            List of Candidate objects sorted by descending score.
        """
        raise NotImplementedError


class AIStrategy(BaseStrategy):
    """AI-driven strategy that delegates to the Context Oracle (LLM)."""

    name: str = "ai"

    def run(
        self,
        hint: str | None = None,
        candidates: list[Candidate] | None = None,
        config: Config | None = None,
        **kwargs: Any,
    ) -> list[Candidate]:
        if not hint or not hint.strip():
            return candidates or []

        config = config or Config()
        count = kwargs.get("count", config.max_candidates)

        from .oracle import generate_candidates

        ai_candidates = generate_candidates(
            hint=hint.strip(),
            count=count,
            model=kwargs.get("model", config.model),
        )

        if candidates:
            seen = {c.value for c in candidates}
            for c in ai_candidates:
                if c.value not in seen:
                    candidates.append(c)
                    seen.add(c.value)
            return sorted(candidates, key=lambda x: x.score, reverse=True)

        return ai_candidates


class DictionaryStrategy(BaseStrategy):
    """Dictionary + mutation strategy using built-in wordlists and user hint words."""

    name: str = "dictionary"

    def run(
        self,
        hint: str | None = None,
        candidates: list[Candidate] | None = None,
        config: Config | None = None,
        **kwargs: Any,
    ) -> list[Candidate]:
        config = config or Config()
        generated: list[Candidate] = []

        # Built-in high-frequency passwords
        common = [
            "password", "123456", "12345678", "qwerty", "abc123", "letmein",
            "admin", "welcome", "monkey", "password1", "123456789", "iloveyou",
            "sunshine", "princess", "flower", "trustno1",
        ]

        # Words extracted from hint
        words: list[str] = []
        if hint:
            words = re.findall(r"\b\w{3,}\b", hint.lower())

        bases = common + words
        for base in bases:
            base = base.strip()
            if not base:
                continue
            generated.append(Candidate(score=0.68, value=base))
            generated.append(Candidate(score=0.62, value=base.capitalize()))
            generated.append(Candidate(score=0.58, value=base + "123"))
            generated.append(Candidate(score=0.55, value=base + "!"))
            generated.append(Candidate(score=0.52, value=base.title() + "2023"))
            generated.append(Candidate(score=0.48, value=base + "2022"))

        # External dictionary if configured
        if config.dictionary_path and Path(config.dictionary_path).is_file():
            try:
                with open(config.dictionary_path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        pw = line.strip()
                        if 4 <= len(pw) <= 32:
                            generated.append(Candidate(score=0.45, value=pw))
            except OSError:
                pass  # ignore missing dictionary

        # Merge with provided candidates, preserving best score per password
        if candidates:
            best: dict[str, Candidate] = {c.value: c for c in candidates}
            for c in generated:
                key = c.value
                if key not in best or c.score > best[key].score:
                    best[key] = c
            merged = list(best.values())
        else:
            merged = generated

        merged = sorted(merged, key=lambda c: c.score, reverse=True)
        return merged[: config.max_candidates]


class MaskStrategy(BaseStrategy):
    """Mask-based strategy focused on dates, years, numeric patterns and leetspeak."""

    name: str = "mask"

    def run(
        self,
        hint: str | None = None,
        candidates: list[Candidate] | None = None,
        config: Config | None = None,
        **kwargs: Any,
    ) -> list[Candidate]:
        config = config or Config()
        generated: list[Candidate] = []

        # Common year patterns (very frequent in passwords)
        for year in range(1990, 2031):
            generated.append(Candidate(score=0.72, value=str(year)))
            generated.append(Candidate(score=0.65, value=f"{year}!"))
            generated.append(Candidate(score=0.60, value=f"{year}!!"))

        # Date combinations
        for y in (1995, 2000, 2005, 2010, 2015, 2020, 2022, 2023):
            for m in range(1, 13):
                for d in (1, 11, 15, 22, 25):
                    for sep in ("", "-", ".", "/"):
                        generated.append(
                            Candidate(score=0.58, value=f"{m:02}{sep}{d:02}{sep}{y}")
                        )
                        generated.append(
                            Candidate(score=0.58, value=f"{y}{sep}{m:02}{sep}{d:02}")
                        )

        # Numeric masks
        for n in range(1000, 10000, 111):
            generated.append(Candidate(score=0.45, value=str(n)))
            generated.append(Candidate(score=0.40, value=str(n) + "00"))

        # Leetspeak mutations on common bases
        bases = ["password", "admin", "secret", "archive", "vacation", "summer"]
        leet = {"a": "@", "e": "3", "i": "1", "o": "0", "s": "$", "t": "7"}
        for base in bases:
            generated.append(Candidate(score=0.50, value=base))
            mutated = base
            for k, v in leet.items():
                mutated = mutated.replace(k, v)
            generated.append(Candidate(score=0.47, value=mutated))
            generated.append(Candidate(score=0.44, value=mutated + "1"))
            generated.append(Candidate(score=0.42, value=mutated.capitalize() + "!"))

        # Incorporate numbers from hint
        if hint:
            numbers = re.findall(r"\d+", hint)
            for num in numbers:
                if len(num) >= 2:
                    generated.append(Candidate(score=0.75, value=num))
                    generated.append(Candidate(score=0.70, value=num + "!"))
                    generated.append(Candidate(score=0.65, value=num + "!!"))

        # Merge with any pre-existing candidates
        if candidates:
            best: dict[str, Candidate] = {c.value: c for c in candidates}
            for c in generated:
                if c.value not in best or c.score > best[c.value].score:
                    best[c.value] = c
            merged = list(best.values())
        else:
            merged = generated

        merged = sorted(merged, key=lambda c: c.score, reverse=True)
        return merged[: config.max_candidates * 2]


def run_strategy(
    strategy: str = "hybrid",
    candidates: list[Candidate] | None = None,
    archive_path: str | None = None,
    config: Config | None = None,
    hint: str | None = None,
    **kwargs: Any,
) -> list[Candidate]:
    """Public entrypoint to run a named strategy or hybrid combination.

    Hybrid runs AI → Dictionary → Mask in sequence, merges results,
    removes duplicates (keeping highest score) and returns the top N candidates.

    Args:
        strategy: One of "ai", "dictionary", "mask", "hybrid", "ai_mask_dictionary".
        candidates: Seed candidates (used by hybrid).
        archive_path: Archive path (reserved for future context-aware strategies).
        config: Configuration object.
        hint: User-provided contextual memory.
        **kwargs: Passed through to concrete strategies.

    Returns:
        Ranked list of Candidate objects (highest score first).
    """
    if candidates is None:
        candidates = []
    config = config or Config()

    strategy = strategy.lower().strip()

    if strategy in ("ai", "ai_only"):
        return AIStrategy().run(
            hint=hint, candidates=candidates, config=config, **kwargs
        )

    if strategy == "dictionary":
        return DictionaryStrategy().run(
            hint=hint, candidates=candidates, config=config, **kwargs
        )

    if strategy == "mask":
        return MaskStrategy().run(
            hint=hint, candidates=candidates, config=config, **kwargs
        )

    # Hybrid strategies combine multiple generators
    if strategy in ("hybrid", "ai_hybrid", "ai_mask_dictionary"):
        # AI first if hint supplied and we have no candidates yet
        if hint and not candidates:
            candidates = AIStrategy().run(
                hint=hint,
                count=max(30, config.max_candidates // 2),
                config=config,
                **kwargs,
            )

        # Dictionary augmentation
        candidates = DictionaryStrategy().run(
            hint=hint, candidates=candidates, config=config, **kwargs
        )

        # Mask augmentation
        candidates = MaskStrategy().run(
            hint=hint, candidates=candidates, config=config, **kwargs
        )

    # Final ranking + limit
    seen: dict[str, float] = {}
    unique: list[Candidate] = []
    for c in candidates:
        key = c.value
        if key not in seen or c.score > seen[key]:
            seen[key] = c.score
            unique.append(c)

    unique.sort(key=lambda c: c.score, reverse=True)
    return unique[: config.max_candidates]


def get_strategy(name: str) -> BaseStrategy:
    """Return instantiated strategy by name (for future plugin system)."""
    registry = {
        "ai": AIStrategy,
        "dictionary": DictionaryStrategy,
        "mask": MaskStrategy,
    }
    if name not in registry:
        raise ValueError(
            f"Unknown strategy '{name}'. "
            f"Available: {list(registry.keys())} (or use 'hybrid')"
        )
    return registry[name]()


__all__ = [
    "BaseStrategy",
    "AIStrategy",
    "DictionaryStrategy",
    "MaskStrategy",
    "run_strategy",
    "get_strategy",
]
