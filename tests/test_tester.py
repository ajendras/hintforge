"""Tests for the tester module including format handlers and strategies."""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from src.hintforge.tester import try_password, extract_hash
from src.hintforge.models import Candidate, Config
from src.hintforge.strategies import run_strategy, HashcatStrategy
from src.hintforge.handlers import detect_format, PasswordError


def test_extract_hash(mocker):
    """Test hash extraction using JohnTheRipper tools (now uses open explicitly)."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(stdout="dummyhash:abc123\n", stderr="")
    mock_file = mocker.patch("builtins.open", mock_open())
    hash_path = extract_hash("tests/fixtures/protected.zip", forced_format="zip")
    assert hash_path.endswith(".hash")
    mock_file.assert_called_once()
    mock_run.assert_called_once()


def test_hashcat_strategy(mocker):
    """Test HashcatStrategy returns candidates (mocks availability)."""
    mocker.patch("src.hintforge.utils.is_hashcat_available", return_value=True)
    mocker.patch(
        "src.hintforge.utils.run_hashcat",
        return_value=[Candidate(score=0.8, value="Hash2022!")],
    )
    result = HashcatStrategy().run(
        hint="test hash", archive_path="dummy.7z", config=Config()
    )
    assert len(result) >= 1


def test_run_strategy_hashcat(mocker):
    """Test hybrid run_strategy with hashcat (mocks AI and hashcat to avoid connection error)."""
    mocker.patch(
        "src.hintforge.oracle.generate_candidates",
        return_value=[Candidate(score=0.9, value="AIpass2022")],
    )
    mocker.patch("src.hintforge.utils.is_hashcat_available", return_value=True)
    mocker.patch(
        "src.hintforge.utils.run_hashcat",
        return_value=[Candidate(score=0.75, value="HCPass!")],
    )
    config = Config(enabled_strategies=["ai", "hashcat"], max_candidates=10)
    candidates = run_strategy(
        strategy="hybrid",
        hint="test",
        candidates=None,
        config=config,
        archive_path="dummy.rar",
    )
    assert len(candidates) >= 1


def test_office_format(mocker, tmp_path):
    """Test office format support (uses temp file to avoid FileNotFoundError)."""
    office_file = tmp_path / "doc.xlsx"
    office_file.write_bytes(b"PK\x03\x04dummy office content")
    mocker.patch(
        "src.hintforge.tester.open_with_password",
        return_value=MagicMock(),  # no exception = success for test
    )
    mocker.patch("src.hintforge.tester.detect_format", return_value="office")
    result = try_password(str(office_file), "officepass")
    assert result is True


def test_candidate():
    """Test Candidate model used throughout tester/strategies."""
    c = Candidate(score=0.95, value="Secret123!", metadata={"source": "ai"})
    assert c.score == 0.95
    assert c.value == "Secret123!"
    assert "Secret123!" in str(c)


def test_try_password_zip(mocker, tmp_path):
    """Test ZIP password trial with mocked handler."""
    zip_file = tmp_path / "test.zip"
    zip_file.write_bytes(b"PK\x03\x04dummy")
    mocker.patch("src.hintforge.tester.open_with_password", return_value=MagicMock())
    assert try_password(str(zip_file), "testpass") is True


def test_try_password_raises_on_bad_password(mocker, tmp_path):
    """Test PasswordError propagation for incorrect passwords."""
    zip_file = tmp_path / "bad.zip"
    zip_file.write_bytes(b"PK\x03\x04dummy")
    mocker.patch(
        "src.hintforge.tester.open_with_password",
        side_effect=PasswordError("Incorrect password"),
    )
    assert try_password(str(zip_file), "wrong") is False
