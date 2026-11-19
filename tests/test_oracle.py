"""Tests for the Context Oracle."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hintforge.oracle import (
    generate_candidates,
    extract_context,
    _parse_llm_response,
)
from hintforge.models import Candidate


def test_parse_llm_response_json():
    text = '[{"password": "Fluffy2023", "score": 0.92}, {"password": "MaxTheDog!", "score": 0.85}]'
    candidates = _parse_llm_response(text, 5)
    assert len(candidates) == 2
    assert candidates[0].value == "Fluffy2023"
    assert candidates[0].score == 0.92


def test_parse_llm_response_fallback():
    text = "1. vacation2022\n2. DogName2020!"
    candidates = _parse_llm_response(text, 3)
    assert len(candidates) >= 1
    assert any("vacation2022" in c.value for c in candidates)


def test_parse_llm_response_synthetic():
    text = "short"
    candidates = _parse_llm_response(text, 2)
    assert len(candidates) == 2


@patch("ollama.chat")
def test_generate_candidates(mock_chat: MagicMock):
    mock_response = {
        "message": {
            "content": json.dumps(
                [
                    {"password": "Buddy2021", "score": 0.95},
                    {"password": "SummerVacation!", "score": 0.88},
                ]
            )
        }
    }
    mock_chat.return_value = mock_response

    candidates = generate_candidates("my dog buddy vacation", count=2, model="llama3")
    assert len(candidates) == 2
    assert candidates[0].value == "Buddy2021"
    assert candidates[0].score >= 0.9
    mock_chat.assert_called_once()


def test_extract_context_filename(tmp_path: Path):
    archive = tmp_path / "family_vacation_2022_dog.rar"
    archive.touch()
    (tmp_path / "memo.txt").write_text("The password includes our dog named Rocky born in 2018.")

    ctx = extract_context(str(archive))
    assert "family" in ctx
    assert "vacation" in ctx
    assert "2022" in ctx
    assert any(w in ctx for w in ("rocky", "dog", "2018"))


def test_extract_context_no_archive():
    assert extract_context("") == ""
    assert extract_context("/non/existent/path.zip") == ""


@patch("exifread.process_file")
def test_extract_context_exif(mock_process: MagicMock, tmp_path: Path):
    mock_process.return_value = {
        "EXIF DateTimeOriginal": "2022:06:15 12:00:00",
        "Image Model": "Canon EOS",
    }
    archive = tmp_path / "photo.jpg"
    archive.touch()

    ctx = extract_context(str(archive))
    assert "2022" in ctx
    assert any(word in ctx.lower() for word in ("canon", "eos"))
