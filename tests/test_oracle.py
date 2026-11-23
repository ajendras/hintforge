"""Tests for the Context Oracle."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hintforge.models import Candidate
from hintforge.oracle import (
    _parse_llm_response,
    extract_context,
    generate_candidates,
)


def test_parse_llm_response_valid():
    valid_json = """[
        {"value": "MaxTheDog2023!", "score": 0.92},
        {"value": "VacationDog2023!", "score": 0.85}
    ]"""
    candidates = _parse_llm_response(valid_json, requested_count=5)
    assert len(candidates) == 2
    assert candidates[0].value == "MaxTheDog2023!"
    assert candidates[0].score == 0.92
    assert isinstance(candidates[0], Candidate)


def test_parse_llm_response_fallback():
    text = "Some text mentioning passwords like: DogVacation2023, MyMax2020!"
    candidates = _parse_llm_response(text, requested_count=3)
    assert len(candidates) >= 1
    assert any("2023" in c.value or "2020" in c.value for c in candidates)


def test_extract_context_filename_only(tmp_path):
    archive = tmp_path / "my_vacation_dog_2023.pdf"
    archive.touch()
    context = extract_context(str(archive))
    assert "2023" in context
    assert "vacation" in context.lower()
    assert "dog" in context.lower()


def test_extract_context_exif(tmp_path, mocker):
    archive = tmp_path / "photo.jpg"
    archive.touch()
    mock_tags = {
        "ImageDescription": "Our family vacation with Max the dog in 2023"
    }
    mocker.patch("hintforge.oracle.exifread.process_file", return_value=mock_tags)
    context = extract_context(str(archive))
    lowered = context.lower()
    assert "vacation" in lowered
    assert any(k in lowered for k in ("2023", "dog", "max"))


def test_extract_context_pdf_metadata(tmp_path, mocker):
    archive = tmp_path / "document.pdf"
    archive.touch()
    mock_pdf = MagicMock()
    mock_pdf.docinfo = {
        "/Title": "Vacation Photos 2023",
        "/Subject": "Dog named Max",
    }
    mock_open = mocker.patch("hintforge.oracle.pikepdf.open")
    mock_open.return_value.__enter__.return_value = mock_pdf
    context = extract_context(str(archive))
    lowered = context.lower()
    assert any(k in lowered for k in ("vacation", "2023", "dog", "max"))


def test_generate_candidates(mocker):
    mock_response = {"response": '[{"value": "TestPass123!", "score": 0.9}]'}
    mocker.patch("hintforge.oracle.ollama.generate", return_value=mock_response)
    mocker.patch("hintforge.oracle.load_config")
    candidates = generate_candidates("test hint", count=1, model="llama3")
    assert len(candidates) >= 1
    assert isinstance(candidates[0], Candidate)
    assert candidates[0].value == "TestPass123!"
