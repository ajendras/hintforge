"""Unit tests for the Context Oracle module."""

import pytest
from unittest.mock import patch, MagicMock

import ollama
from src.hintforge.oracle import (
    generate_candidates,
    _parse_llm_response,
    _build_system_prompt,
    _build_user_prompt,
    _extract_json_block,
)
from src.hintforge.models import Candidate


def test_parse_llm_response_json():
    """Test parsing valid JSON response from LLM."""
    text = """[
        {"password": "Max2022!", "score": 0.92},
        {"password": "VacationDog23", "score": 0.85}
    ]"""
    result = _parse_llm_response(text, 5)
    assert len(result) == 2
    assert result[0].value == "Max2022!"
    assert result[0].score == 0.92


def test_parse_llm_response_synthetic():
    """Test synthetic candidate generation fallback (now guaranteed >=2)."""
    result = _parse_llm_response("2022", 3)
    assert len(result) >= 2
    values = [c.value for c in result]
    assert any("2022" in v for v in values)


def test_extract_json_block():
    """Test JSON block extraction helper."""
    text = 'Some text before [{"password":"foo","score":0.9}] and after.'
    block = _extract_json_block(text)
    assert block is not None
    assert "foo" in block


def test_generate_candidates_empty_response(mocker):
    """Test handling of empty LLM response falls back to synthetic candidates."""
    mock_chat = mocker.patch("ollama.chat")
    mock_chat.return_value = {"message": {"content": ""}}
    candidates = generate_candidates("test hint", count=3)
    assert len(candidates) >= 2


def test_generate_candidates_connection_error(mocker):
    """Test connection error is translated to user-friendly RuntimeError."""
    mock_chat = mocker.patch("ollama.chat")
    mock_chat.side_effect = Exception("Connection refused")
    with pytest.raises(RuntimeError, match="Could not connect to Ollama"):
        generate_candidates("any hint", count=3)


def test_generate_candidates(mocker):
    """Test normal successful candidate generation and parsing."""
    mock_chat = mocker.patch("ollama.chat")
    mock_chat.return_value = {
        "message": {
            "content": '[{"password": "Dog2023!", "score": 0.88}, {"password": "2023Vacation", "score": 0.75}]'
        }
    }
    candidates = generate_candidates("my dog vacation 2023", count=5, model="llama3")
    assert len(candidates) == 2
    assert candidates[0].score > candidates[1].score
    assert candidates[0].value == "Dog2023!"


def test_build_prompts():
    """Test prompt builders produce expected strings."""
    system = _build_system_prompt()
    assert "password recovery specialist" in system
    user = _build_user_prompt("dog 2022", 10)
    assert "dog 2022" in user
    assert "exactly 10" in user
