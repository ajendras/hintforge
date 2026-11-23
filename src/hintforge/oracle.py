"""Context Oracle for HintForge.

Uses local Ollama LLM to turn natural language hints (augmented by
auto-extracted context from filename, nearby text, EXIF and PDF metadata)
into ranked Candidate objects. Includes robust JSON parsing with fallback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import exifread
import ollama
import pikepdf

from .models import Candidate
from .utils import load_config


def _parse_llm_response(response_text: str, requested_count: int = 10) -> list[Candidate]:
    """Parse LLM output into a list of Candidate objects.

    Supports structured JSON arrays and falls back to regex extraction of
    password-like strings. Limits results to requested_count.
    """
    candidates: list[Candidate] = []
    try:
        json_match = re.search(r"\[\s*\{.*\}\s*\]", response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            for item in data[:requested_count]:
                if isinstance(item, dict):
                    val = item.get("value") or item.get("password") or str(item)
                    score = float(item.get("score", 0.5))
                    if isinstance(val, str) and val.strip():
                        candidates.append(Candidate(value=val.strip(), score=score))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    if not candidates:
        # fallback regex for markdown/lists of likely passwords
        passwords = re.findall(
            r"[\"']?([A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>/?]{5,})[\"']?",
            response_text,
        )
        for i, pw in enumerate(passwords[:requested_count]):
            score = max(0.9 - i * 0.08, 0.3)
            candidates.append(Candidate(value=pw, score=score))

    return candidates[:requested_count]


def extract_context(archive_path: str) -> str:
    """Extract context terms from filename, nearby text files, EXIF and PDF metadata.

    Returns a space-separated string of unique terms (lowercased). Years and
    alphanumeric tokens are prioritised. Gracefully degrades on missing
    libraries or unreadable files.
    """
    terms: set[str] = set()
    path = Path(archive_path)
    if not path.exists():
        return path.stem.lower().replace("_", " ").replace("-", " ")

    # Filename tokens and years
    stem = path.stem
    words = re.findall(r"[A-Za-z0-9]+", stem)
    for w in words:
        if len(w) > 2:
            terms.add(w.lower())
    for year in re.findall(r"(19|20)\d{2}", stem):
        terms.add(year)

    # Nearby text files
    for text_file in list(path.parent.glob("*.txt")) + list(path.parent.glob("*.md")):
        try:
            content = text_file.read_text(encoding="utf-8", errors="ignore")[:1000]
            for w in re.findall(r"[A-Za-z0-9]{3,}", content):
                if len(w) > 2:
                    terms.add(w.lower())
        except Exception:
            continue

    # EXIF metadata for images
    if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".tiff"):
        try:
            with open(path, "rb") as f:
                tags = exifread.process_file(f, details=False, stop_tag="EXIF")
                for tag_name, tag_value in tags.items():
                    name_lower = str(tag_name).lower()
                    if any(k in name_lower for k in ("image", "description", "comment", "artist")):
                        val = str(tag_value).strip()
                        if val and len(val) < 200:
                            for w in re.findall(r"\w{3,}", val):
                                terms.add(w.lower())
        except Exception:
            pass

    # PDF metadata
    if path.suffix.lower() == ".pdf":
        try:
            with pikepdf.open(path) as pdf:
                if hasattr(pdf, "docinfo") and pdf.docinfo:
                    for key, value in pdf.docinfo.items():
                        val_str = str(value).strip()
                        if val_str and len(val_str) < 200:
                            for w in re.findall(r"[A-Za-z0-9]{3,}", val_str):
                                terms.add(w.lower())
        except Exception:
            pass

    if not terms:
        return stem.lower().replace("_", " ").replace("-", " ")
    return " ".join(sorted(terms))


def generate_candidates(
    hint: str,
    count: int = 50,
    model: str = "llama3",
    archive_path: str | None = None,
) -> list[Candidate]:
    """Generate password candidates using local LLM, augmented by extracted context.

    If archive_path is supplied, extract_context() automatically enriches the
    prompt with filename, nearby text, EXIF and PDF metadata.
    """
    config = load_config()
    effective_model = model or config.model
    effective_count = count or config.max_candidates

    enriched_hint = hint
    if archive_path:
        context = extract_context(archive_path)
        if context:
            enriched_hint = f"{hint}. Additional context: {context}."

    prompt = f"""You are an expert password recovery assistant.
Hint: "{enriched_hint}"

Generate exactly {effective_count} plausible password candidates that a human
would create from this memory. Vary casing, add symbols/numbers, combine words.

Return ONLY a valid JSON array:
[
  {{"value": "MaxDog2023!", "score": 0.92}},
  ...
]
No extra text or explanations."""

    try:
        response = ollama.generate(
            model=effective_model,
            prompt=prompt,
            options={
                "temperature": config.temperature,
                "top_p": getattr(config, "top_p", 0.9),
            },
        )
        response_text = response.get("response", "")
        candidates = _parse_llm_response(response_text, effective_count)
        if not candidates:
            raise ValueError("No candidates parsed from LLM")
    except Exception:
        # lightweight deterministic fallback when Ollama is unavailable
        candidates = []
        bases = re.findall(r"\w+", enriched_hint.lower())
        numbers = re.findall(r"\d+", enriched_hint)
        for i in range(effective_count):
            pw_parts = [w.capitalize() for w in bases[:3]]
            pw = "".join(pw_parts)
            if numbers:
                pw += numbers[0]
            pw += "!" if i % 3 == 0 else "2023"
            score = max(0.85 - i * 0.03, 0.35)
            candidates.append(Candidate(value=pw, score=score))

    min_threshold = getattr(config, "min_score_threshold", 0.25)
    filtered = [c for c in candidates if c.score >= min_threshold]
    return sorted(filtered, key=lambda c: c.score, reverse=True)[:effective_count]
