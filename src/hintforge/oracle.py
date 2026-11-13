"""Context Oracle — local LLM integration for HintForge.

Uses Ollama to convert vague human memories/hints into intelligently
ranked password candidates. Employs structured JSON prompting with
robust fallback parsing for reliability across different models.
"""

from __future__ import annotations

import json
import re
from typing import Any

import ollama
from pydantic import ValidationError

from .models import Candidate


def _build_system_prompt() -> str:
    """Return the system prompt that steers the LLM toward structured output."""
    return (
        "You are a password recovery specialist. "
        "Given a user's vague memory about their archive password, "
        "generate plausible candidates by combining words, dates, names, "
        "pets, locations and common mutations (numbers, symbols, capitalization). "
        "Respond with **only** a valid JSON array of objects. "
        "Each object must have 'password' (string) and 'score' (float 0.0-1.0). "
        "Never add explanations, markdown or extra text."
    )


def _build_user_prompt(hint: str, count: int) -> str:
    """Construct the user prompt with concrete instructions."""
    return (
        f"Memory/hint: \"{hint}\"\n\n"
        f"Generate exactly {count} realistic password candidates. "
        "Vary length, composition and complexity. Prioritise high-likelihood patterns "
        "the user would actually choose. Output ONLY the JSON array."
    )


def _extract_json_block(text: str) -> str | None:
    """Robustly locate the largest JSON array in the LLM response."""
    # Look for anything that looks like a JSON array
    matches = re.findall(r"(\[\s*\{.*?\}\s*\])", text, re.DOTALL)
    if not matches:
        # Broader fallback
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return match.group()
        return None
    # Return the longest match (most likely the full array)
    return max(matches, key=len)


def _parse_llm_response(text: str, requested_count: int) -> list[Candidate]:
    """Parse LLM output into Candidate objects. Falls back to line-based parsing."""
    text = text.strip()
    if not text:
        return []

    json_block = _extract_json_block(text)
    candidates: list[Candidate] = []

    if json_block:
        try:
            data: Any = json.loads(json_block)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        pw = item.get("password") or item.get("pw") or str(item.get("value", ""))
                        score = float(item.get("score", item.get("likelihood", 0.65)))
                        if isinstance(pw, str) and pw.strip():
                            score = max(0.1, min(0.99, score))
                            candidates.append(Candidate(score=score, value=pw.strip()))
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
            pass

    # Fallback: line-by-line extraction when JSON parsing fails
    if not candidates:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for i, line in enumerate(lines[:requested_count]):
            # Remove rank prefixes, quotes, etc.
            cleaned = re.sub(r"^[0-9\.\-\s\*\>]+", "", line)
            cleaned = cleaned.strip("\"'`[]{}")
            # Take first token that looks like a password
            pw_match = re.search(r"([A-Za-z0-9!@#$%^&*()\-_=+[\]{}|;:'\",.<>/?]{4,30})", cleaned)
            if pw_match:
                pw = pw_match.group(1)
                score = max(0.25, 0.92 - (i * 0.018))
                candidates.append(Candidate(score=score, value=pw))

    # If still empty, create synthetic candidates from the hint itself
    if not candidates and hint := re.sub(r"[^A-Za-z0-9 ]", "", text.lower()):
        words = hint.split()[:5]
        base = "".join(words)
        synthetic = [
            base,
            base + "2022",
            base.title() + "!",
            "".join(w.capitalize() for w in words),
        ]
        for i, pw in enumerate(synthetic[:requested_count]):
            candidates.append(Candidate(score=0.75 - i * 0.1, value=pw))

    # Deduplicate while preserving order/score
    seen: set[str] = set()
    unique: list[Candidate] = []
    for c in candidates:
        if c.value not in seen:
            seen.add(c.value)
            unique.append(c)

    return sorted(unique, key=lambda c: c.score, reverse=True)


def generate_candidates(
    hint: str, count: int = 50, model: str = "llama3"
) -> list[Candidate]:
    """Generate ranked password candidates from a natural-language hint using Ollama.

    The LLM is prompted to return structured JSON. Response is parsed robustly
    with a line-based fallback. Candidates are deduplicated and sorted by
    descending likelihood score.

    Args:
        hint: Contextual memory provided by the user (e.g. "dog name 2019 vacation")
        count: Desired number of candidates (capped at 200 for practicality)
        model: Ollama model identifier (must be pulled locally)

    Returns:
        List of Candidate objects sorted by score (highest first).

    Raises:
        ValueError: If hint is empty or invalid.
        RuntimeError: If Ollama is unreachable or returns an error.
    """
    if not hint or not hint.strip():
        raise ValueError("Hint cannot be empty or whitespace-only.")

    count = max(1, min(200, count))  # sensible bounds

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": _build_user_prompt(hint.strip(), count)},
    ]

    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.75,
                "top_p": 0.9,
                "num_predict": 1536,
                "stop": ["```", "\n\n\n"],
            },
        )
        content = response.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty response from Ollama")

        candidates = _parse_llm_response(content, count)

        # Guarantee we return at least a few results
        if not candidates:
            candidates = [
                Candidate(score=0.85, value=hint.strip().replace(" ", "")),
                Candidate(score=0.72, value=hint.strip().title() + "2023"),
            ]

        return candidates[:count]

    except ollama.ResponseError as exc:
        raise RuntimeError(f"Ollama model error ({model}): {exc}") from exc
    except ollama.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to Ollama. Is it running? (ollama serve)"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Unexpected error during candidate generation: {exc}") from exc


__all__ = ["generate_candidates"]
