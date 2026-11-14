"""Tests for the Context Oracle.

Covers prompt building, response parsing (JSON + fallbacks), validation,
and mocked LLM interaction. Uses stdlib unittest.mock to avoid needing
a live Ollama server in CI.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from hintforge.models import Candidate
from hintforge.oracle import (
    generate_candidates,
    _parse_llm_response,
    _build_system_prompt,
    _build_user_prompt,
)


def test_build_prompts() -> None:
    """Test that system and user prompts contain expected guidance."""
    system = _build_system_prompt()
    assert "password recovery specialist" in system
    assert "valid JSON array" in system
    assert "score" in system

    user = _build_user_prompt("my dog max vacation 2022", 12)
    assert "my dog max vacation 2022" in user
    assert "exactly 12" in user
    assert "Output ONLY the JSON array" in user


def test_parse_llm_response_json() -> None:
    """Parse well-formed JSON array from LLM."""
    json_text = (
        '[{"password": "Dog2023!", "score": 0.95}, '
        '{"password": "SummerVacation", "score": 0.8}]'
    )
    candidates = _parse_llm_response(json_text, 5)
    assert len(candidates) == 2
    assert candidates[0].value == "Dog2023!"
    assert candidates[0].score == 0.95
    assert candidates[1].value == "SummerVacation"
    assert candidates[1].score == 0.8


def test_parse_llm_response_fallback() -> None:
    """Line-by-line fallback when JSON extraction fails."""
    text = "1. MyDog2020!\n2. Vacation2022\nRank 3: MaxTheDog"
    candidates = _parse_llm_response(text, 5)
    assert len(candidates) >= 2
    values = {c.value for c in candidates}
    assert "MyDog2020!" in values
    assert any("Vacation2022" in v for v in values)


def test_parse_llm_response_synthetic() -> None:
    """Synthetic candidates generated from hint text when everything else fails."""
    text = "my dog max 2022"
    candidates = _parse_llm_response(text, 4)
    assert len(candidates) >= 2
    assert any("mydogmax2022" in c.value.lower() for c in candidates)
    assert all(isinstance(c, Candidate) for c in candidates)
    assert all(0.0 <= c.score <= 1.0 for c in candidates)


def test_generate_candidates_validation() -> None:
    """Empty hint is rejected."""
    with pytest.raises(ValueError, match="Hint cannot be empty"):
        generate_candidates("")
    with pytest.raises(ValueError, match="Hint cannot be empty"):
        generate_candidates("   ")


@patch("hintforge.oracle.ollama.chat")
def test_generate_candidates_mocked(mock_chat: MagicMock) -> None:
    """Full generation path with mocked Ollama response."""
    mock_content = (
        '[{"password":"TestPass123","score":0.92},'
        '{"password":"Hint2023!","score":0.85}]'
    )
    mock_chat.return_value = {"message": {"content": mock_content}}

    candidates = generate_candidates(
        hint="my test archive password", count=10, model="llama3"
    )

    assert len(candidates) == 2
    assert candidates[0].value == "TestPass123"
    assert candidates[0].score == 0.92
    assert candidates[1].value == "Hint2023!"
    mock_chat.assert_called_once()
    # verify ordering
    assert candidates[0].score > candidates[1].score


@patch("hintforge.oracle.ollama.chat")
def test_generate_candidates_empty_response(mock_chat: MagicMock) -> None:
    """Graceful fallback when Ollama returns no usable content."""
    mock_chat.return_value = {"message": {"content": ""}}

    candidates = generate_candidates("some hint about my dog", count=5)

    assert len(candidates) >= 2
    assert all(isinstance(c, Candidate) for c in candidates)
    # synthetic candidates based on the original hint
    assert any("dog" in c.value.lower() for c in candidates)


@patch("hintforge.oracle.ollama.chat")
def test_generate_candidates_connection_error(mock_chat: MagicMock) -> None:
    """Connection errors are wrapped in RuntimeError."""
    mock_chat.side_effect = Exception("Connection refused")

    with pytest.raises(RuntimeError, match="Unexpected error during candidate generation"):
        generate_candidates("any hint", count=3)
