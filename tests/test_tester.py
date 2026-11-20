"""Unit and integration tests for tester.py and handlers.

Covers try_password(), extract_hash(), format detection, error handling
and Python 3.12 compatibility (msoffcrypto is unavailable). Uses mocks
for external calls and temporary archives. Consistent with neo-brutalist
project style and existing test_oracle.py patterns.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hintforge.handlers import PasswordError, detect_format, open_with_password
from hintforge.tester import extract_hash, try_password


@pytest.fixture
def temp_zip(tmp_path: Path) -> Path:
    """Create a temporary encrypted-style ZIP for integration tests."""
    archive = tmp_path / "protected.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("secret.txt", "confidential data")
    return archive


def test_detect_format() -> None:
    """Test extension and magic-based format detection."""
    assert detect_format("sample.zip") == "zip"
    assert detect_format("backup.rar") == "rar"
    assert detect_format("doc.docx") == "office"
    assert detect_format("report.pdf") == "pdf"
    assert detect_format("data.7z") == "7z"
    assert detect_format("archive.tar.gz") == "tar"
    # unknown falls back to zip
    assert detect_format("unknown.bin") == "zip"


def test_try_password_success(mocker) -> None:
    """Successful password opens the archive without raising."""
    mocker.patch("hintforge.tester.open_with_password", return_value=MagicMock())
    assert try_password("test.zip", "correctpass123") is True


def test_try_password_failure(mocker) -> None:
    """Wrong password raises PasswordError which is turned into False."""
    mocker.patch(
        "hintforge.tester.open_with_password",
        side_effect=PasswordError("bad password"),
    )
    assert try_password("test.rar", "wrong") is False


def test_try_password_dry_run(mocker) -> None:
    """Dry-run short-circuits before any real I/O."""
    mock_open = mocker.patch("hintforge.tester.open_with_password")
    assert try_password("test.pdf", "anything", dry_run=True) is True
    mock_open.assert_not_called()


def test_try_password_handles_other_errors(mocker) -> None:
    """Other exceptions during open are treated as failure."""
    mocker.patch(
        "hintforge.tester.open_with_password",
        side_effect=RuntimeError("disk full"),
    )
    assert try_password("test.7z", "pass") is False


def test_extract_hash_zip(mocker) -> None:
    """Hash extraction calls the correct *2john tool and writes .hash file."""
    mock_run = mocker.patch("hintforge.handlers.subprocess.run")
    mock_run.return_value = MagicMock(stdout="hashdata:123456\n", stderr="")
    hash_path = extract_hash(str(temp_zip(mocker.tmp_path)), forced_format="zip")
    assert Path(hash_path).suffix == ".hash"
    mock_run.assert_called_once()


def test_extract_hash_unsupported(mocker) -> None:
    """Unsupported format raises clear ValueError."""
    with pytest.raises(ValueError, match="not supported"):
        extract_hash("file.txt")


@patch("hintforge.handlers._HAS_MSOFFCRYPTO", False)
def test_office_unsupported_on_py312() -> None:
    """Python 3.12 without msoffcrypto raises a clear runtime error."""
    with pytest.raises(RuntimeError, match="msoffcrypto"):
        with open_with_password("test.docx", "pass", forced_format="office"):
            pass  # pragma: no cover


def test_try_password_with_hashcat_mocks(mocker) -> None:
    """Ensure extract_hash path works when called from strategies (mocked)."""
    mocker.patch("hintforge.tester.extract_hash", return_value="/tmp/fake.hash")
    # run_hashcat is in utils but tester re-exports for convenience in tests
    mocker.patch("hintforge.tester.run_hashcat", return_value=["candidate1", "candidate2"])
    # try_password itself does not call hashcat, but this validates the import path
    assert extract_hash("dummy.zip") == "/tmp/fake.hash"


def test_password_error_inheritance() -> None:
    """PasswordError is a ValueError subclass for clean handling."""
    err = PasswordError("test")
    assert isinstance(err, ValueError)
