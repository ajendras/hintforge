"""Tests for the Context Oracle (LLM candidate generation).

Uses pytest and pytest-mock to test JSON parsing, fallback logic,
scoring, deduplication, input validation and error wrapping.
Mocked Ollama responses guarantee reproducible tests.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.hintforge.models import Candidate
from src.hintforge.oracle import (
    _build_system_prompt,
    _build_user_prompt,
    _extract_json_block,
    _parse_llm_response,
    generate_candidates,
)


def test_build_system_prompt() -> None:
    """System prompt contains required instructions for structured output."""
    prompt = _build_system_prompt()
    assert "password recovery specialist" in prompt.lower()
    assert "valid JSON array" in prompt
    assert "password" in prompt and "score" in prompt


def test_build_user_prompt() -> None:
    """User prompt includes the hint and exact count request."""
    prompt = _build_user_prompt("my dog max born 2019", 42)
    assert "my dog max born 2019" in prompt
    assert "exactly 42" in prompt
    assert "Output ONLY the JSON array" in prompt


def test_extract_json_block() -> None:
    """Robust extraction finds JSON array even inside markdown or noise."""
    text = (
        "Here are some ideas:\n"
        "```json\n"
        '[{"password":"Fluffy2020","score":0.92},{"password":"MaxTheDog","score":0.81}]\n'
        "```\n"
        "Hope this helps!"
    )
    block = _extract_json_block(text)
    assert block is not None
    assert "Fluffy2020" in block
    assert "MaxTheDog" in block

    # Plain array with no markdown
    plain = '[{"password":"test","score":0.9}] extra text'
    assert _extract_json_block(plain) is not None


def test_parse_llm_response_json_success() -> None:
    """Valid JSON produces correct Candidate objects with proper ordering."""
    json_str = (
        '[{"password": "Vacation2022!", "score": 0.91}, '
        '{"password": "BuddyTheDog", "score": 0.67}]'
    )
    candidates = _parse_llm_response(json_str, 10)
    assert len(candidates) == 2
    assert candidates[0].value == "Vacation2022!"
    assert candidates[0].score == pytest.approx(0.91)
    assert candidates[1].score == pytest.approx(0.67)
    assert all(isinstance(c, Candidate) for c in candidates)


def test_parse_llm_response_fallback_lines() -> None:
    """Line-by-line parser works when JSON extraction fails."""
    messy = "1. SummerDog22\n2. Fluffy2023!\n3. MyBestFriend"
    candidates = _parse_llm_response(messy, 5)
    assert len(candidates) >= 3
    values = {c.value for c in candidates}
    assert "SummerDog22" in values
    assert any(c.score > 0.7 for c in candidates)


def test_parse_llm_response_synthetic_fallback() -> None:
    """When everything fails we generate synthetic candidates from the hint."""
    garbage = "this is not a json response at all sorry"
    candidates = _parse_llm_response(garbage, 4)
    assert len(candidates) >= 2
    assert all(0.0 <= c.score <= 1.0 for c in candidates)
    assert all(len(c.value) > 3 for c in candidates)


def test_parse_llm_response_deduplication() -> None:
    """Duplicate passwords keep the highest score."""
    text = (
        '[{"password":"abc123","score":0.6},'
        '{"password":"abc123","score":0.9},'
        '{"password":"def","score":0.8}]'
    )
    candidates = _parse_llm_response(text, 10)
    scores = {c.value: c.score for c in candidates}
    assert scores["abc123"] == pytest.approx(0.9)
    assert len(candidates) == 2


@pytest.fixture
def mock_ollama_response():
    """Provide a realistic Ollama chat response for patching."""
    return {
        "message": {
            "content": json.dumps(
                [
                    {"password": "Max2023!", "score": 0.93},
                    {"password": "BeachVacay22", "score": 0.81},
                    {"password": "Doggo2020", "score": 0.74},
                ]
            )
        }
    }


@patch("ollama.chat")
def test_generate_candidates_success(mock_chat, mock_ollama_response) -> None:
    """Full pipeline with mocked Ollama returns sorted Candidates."""
    mock_chat.return_value = mock_ollama_response

    candidates = generate_candidates(
        hint="my dog max and the year we went to the beach",
        count=30,
        model="llama3.1",
    )

    assert len(candidates) == 3
    assert candidates[0].score > candidates[1].score > candidates[2].score
    assert candidates[0].value == "Max2023!"
    assert all(0.0 < c.score <= 1.0 for c in candidates)
    assert all(isinstance(c, Candidate) for c in candidates)
    mock_chat.assert_called_once()


def test_generate_candidates_empty_hint() -> None:
    """Empty or whitespace-only hint is rejected immediately."""
    with pytest.raises(ValueError, match="Hint cannot be empty"):
        generate_candidates("   ")

    with pytest.raises(ValueError, match="Hint cannot be empty"):
        generate_candidates("")


@patch("ollama.chat")
def test_generate_candidates_connection_error(mock_chat) -> None:
    """Ollama ConnectionError is wrapped in a helpful RuntimeError."""
    mock_chat.side_effect = Exception("Failed to connect to Ollama")

    with pytest.raises(RuntimeError, match="Could not connect to Ollama"):
        generate_candidates("test hint", count=5)


@patch("ollama.chat")
def test_generate_candidates_response_error(mock_chat) -> None:
    """ResponseError from Ollama is wrapped with model name."""
    mock_chat.side_effect = Exception("model llama3 not found")

    with pytest.raises(RuntimeError, match="Ollama model error"):
        generate_candidates("hint", model="llama3")


def test_generate_candidates_count_limits() -> None:
    """Count is clamped between 1 and 200."""
    with patch("ollama.chat") as mock_chat:
        mock_chat.return_value = {
            "message": {"content": '[{"password":"a","score":0.5}]'}
        }
        candidates = generate_candidates("hint", count=500)
        assert len(candidates) <= 200

        candidates = generate_candidates("hint", count=0)
        assert len(candidates) >= 1


def test_candidate_str_representation() -> None:
    """Candidate.__str__ produces readable debug output."""
    c = Candidate(score=0.876, value="Secret2023!")
    assert "Secret2023!" in str(c)
    assert "0.876" in str(c)
