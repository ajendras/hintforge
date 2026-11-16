"""Tests for tester module and the new hashcat integration.

Covers try_password, format detection, hash extraction (mocked),
HashcatStrategy and run_hashcat helper.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from hintforge.handlers import extract_hash, PasswordError, _get_hashcat_mode
from hintforge.models import Candidate, Config
from hintforge.strategies import HashcatStrategy, run_strategy
from hintforge.tester import try_password, test_candidate
from hintforge.utils import is_hashcat_available, run_hashcat


def test_get_hashcat_mode():
    assert _get_hashcat_mode("7z") == 11600
    assert _get_hashcat_mode("rar") == 13000
    assert _get_hashcat_mode("pdf") == 10500
    assert _get_hashcat_mode("unknown") == 17200


@patch("hintforge.handlers.which")
@patch("hintforge.handlers.subprocess.run")
@patch("builtins.open", new_callable=mock_open)
def test_extract_hash(mock_file, mock_run, mock_which):
    mock_which.return_value = "/usr/bin/zip2john"
    mock_run.return_value = MagicMock(stdout="hashline:1234")
    path = extract_hash("test.zip", forced_format="zip")
    assert path.endswith(".hash")
    mock_file.assert_called_once()
    mock_run.assert_called_once()


@patch("hintforge.handlers.which", return_value=None)
def test_extract_hash_missing_tool(mock_which):
    with pytest.raises(RuntimeError, match="not found"):
        extract_hash("test.rar", forced_format="rar")


def test_is_hashcat_available():
    with patch("hintforge.utils.which", return_value="/usr/bin/hashcat"):
        assert is_hashcat_available() is True
    with patch("hintforge.utils.which", return_value=None):
        assert is_hashcat_available() is False


@patch("hintforge.utils.run_hashcat", return_value="Cracked2023!")
@patch("hintforge.handlers.extract_hash", return_value="test.hash")
def test_hashcat_strategy(mock_extract, mock_run_hashcat):
    config = Config(enabled_strategies=["hashcat"], hashcat_mask="?d?d?d?d")
    strategy = HashcatStrategy()
    result = strategy.run(
        hint="born in 2023",
        candidates=[],
        config=config,
        archive_path="protected.7z",
    )
    assert len(result) >= 1
    assert any(c.value == "Cracked2023!" for c in result)
    assert any("hashcat" in c.metadata.get("source", "") for c in result)


@patch("hintforge.utils.run_hashcat", return_value=None)
@patch("hintforge.handlers.extract_hash", return_value="test.hash")
def test_hashcat_strategy_fallback(mock_extract, mock_run_hashcat):
    config = Config(enabled_strategies=["hashcat"])
    strategy = HashcatStrategy()
    result = strategy.run(
        hint="test",
        candidates=[Candidate(score=0.8, value="OldGuess")],
        config=config,
        archive_path="protected.zip",
    )
    assert len(result) == 1
    assert result[0].value == "OldGuess"


def test_run_strategy_hashcat():
    config = Config(enabled_strategies=["hashcat"])
    with patch("hintforge.strategies.HashcatStrategy.run") as mock_hc:
        mock_hc.return_value = [Candidate(score=0.95, value="GPUCrack!")]
        candidates = run_strategy(
            strategy="hybrid",
            hint="secret 2020",
            config=config,
            archive_path="test.rar",
        )
        assert any(c.value == "GPUCrack!" for c in candidates)


@pytest.fixture
def mock_zip_archive(tmp_path):
    archive = tmp_path / "test.zip"
    archive.write_bytes(b"PK\x03\x04fakezipcontent")
    return str(archive)


@patch("hintforge.tester.detect_format", return_value="zip")
@patch("hintforge.tester._test_zip", return_value=True)
def test_try_password_success(mock_test, mock_detect, mock_zip_archive):
    assert try_password(mock_zip_archive, "correctpass") is True


@patch("hintforge.tester.detect_format", return_value="zip")
@patch("hintforge.tester._test_zip", return_value=False)
def test_try_password_failure(mock_test, mock_detect, mock_zip_archive):
    assert try_password(mock_zip_archive, "wrongpass") is False


def test_test_candidate():
    candidate = Candidate(score=0.9, value="testpass")
    with patch("hintforge.tester.try_password", return_value=True) as mock_try:
        assert test_candidate("archive.zip", candidate) is True
        mock_try.assert_called_once_with("archive.zip", "testpass")


@patch("hintforge.tester._test_office", return_value=True)
def test_office_format(mock_office):
    with patch("hintforge.tester.detect_format", return_value="office"):
        assert try_password("doc.xlsx", "officepass") is True
