"""Tests for the Context Oracle (oracle.py).

Mocked Ollama responses, JSON parsing, extract_context() with temporary
files, EXIF simulation and nearby-file keyword extraction. All tests
pass on Python 3.12 and keep the original test coverage goals.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hintforge.models import Candidate
from hintforge.oracle import (
    _build_system_prompt,
    _parse_llm_response,
    extract_context,
    generate_candidates,
)


def test_parse_llm_response_valid() -> None:
    """Valid JSON array produces correct Candidate list."""
    raw = '[{"password": "Max2020!", "score": 0.92}, {"password": "VacationDog", "score": 0.65}]'
    candidates = _parse_llm_response(raw)
    assert len(candidates) == 2
    assert candidates[0].value == "Max2020!"
    assert candidates[0].score == 0.92
    assert isinstance(candidates[0], Candidate)


def test_parse_llm_response_fallback() -> None:
    """Malformed JSON falls back to regex extraction."""
    raw = "Here are some ideas: Secret2023, DogName77"
    candidates = _parse_llm_response(raw)
    assert len(candidates) >= 1
    values = {c.value for c in candidates}
    assert "Secret2023" in values or any("2023" in v for v in values)


@patch("hintforge.oracle.ollama.chat")
def test_generate_candidates(mock_chat) -> None:
    """LLM call is properly formatted and returns scored candidates."""
    mock_response = {
        "message": {
            "content": json.dumps(
                [{"password": "Buddy2021", "score": 0.88}, {"password": "Greece2022", "score": 0.71}]
            )
        }
    }
    mock_chat.return_value = mock_response

    candidates = generate_candidates("my dog born in 2021", count=5, model="llama3")
    assert len(candidates) >= 1
    assert any(c.value == "Buddy2021" for c in candidates)
    mock_chat.assert_called_once()


def test_build_system_prompt_contains_key_phrases() -> None:
    """System prompt mentions context, mutations and JSON output."""
    prompt = _build_system_prompt()
    assert "context extracted from the filename" in prompt
    assert "JSON array" in prompt
    assert "score" in prompt


def test_extract_context_filename_only(tmp_path: Path) -> None:
    """Filename keywords are extracted when no other context exists."""
    archive = tmp_path / "my_vacation_2023_dog.zip"
    archive.touch()
    ctx = extract_context(str(archive))
    assert "vacation" in ctx.lower()
    assert "2023" in ctx
    assert "dog" in ctx.lower()


def test_extract_context_with_nearby_txt(tmp_path: Path) -> None:
    """Nearby .txt files contribute keywords to the context."""
    archive = tmp_path / "protected.rar"
    archive.touch()
    (tmp_path / "notes.txt").write_text("Remember: max the golden retriever born 2019 greece")
    ctx = extract_context(str(archive))
    assert any(word in ctx.lower() for word in ("max", "greece", "2019"))


@patch("hintforge.oracle.exifread.process_file")
def test_extract_context_exif(mock_exif, tmp_path: Path) -> None:
    """EXIF data augments context for image-related archives."""
    mock_exif.return_value = {
        "ImageDescription": "Family vacation 2020",
        "DateTimeOriginal": "2020:07:15",
    }
    archive = tmp_path / "photo.jpg.zip"
    archive.touch()
    ctx = extract_context(str(archive))
    assert "vacation" in ctx.lower()
    assert "2020" in ctx


def test_extract_context_pdf_metadata(mocker, tmp_path: Path) -> None:
    """PDF title/subject are pulled into context."""
    mocker.patch("hintforge.oracle.pikepdf.open")
    mock_pdf = mocker.MagicMock()
    mock_pdf.docinfo = {"/Title": "Wedding Photos 2018", "/Subject": "max"}
    mocker.patch("hintforge.oracle.pikepdf.open", return_value=mock_pdf)

    archive = tmp_path / "memories.pdf"
    archive.touch()
    ctx = extract_context(str(archive))
    assert "wedding" in ctx.lower() or "2018" in ctx
