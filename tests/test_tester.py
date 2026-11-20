"""Tests for tester.py and related handlers functionality.

Covers try_password success/failure paths, hash extraction for hashcat,
format detection, and office support with explicit 3.12 skip (msoffcrypto
is not available on Python 3.12+ per pyproject.toml extras).
Uses pytest-mock for subprocess, open_with_password, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hintforge.handlers import (
    PasswordError,
    _HAS_MSOFFCRYPTO,
    detect_format,
    extract_hash,
    open_with_password,
)
from hintforge.tester import try_password


def test_try_password_success(mocker):
    """Successful password returns True."""
    mock_cm = mocker.patch("hintforge.tester.open_with_password")
    mock_cm.return_value.__enter__.return_value = MagicMock()

    assert try_password("test.zip", "correct") is True
    mock_cm.assert_called_once_with("test.zip", "correct", forced_format=None)


def test_try_password_failure(mocker):
    """Wrong password returns False via PasswordError."""
    mocker.patch(
        "hintforge.tester.open_with_password",
        side_effect=PasswordError("bad pw"),
    )
    assert try_password("test.rar", "wrong") is False


def test_try_password_propagates_unexpected_error(mocker):
    """Unexpected errors are wrapped in RuntimeError."""
    mocker.patch(
        "hintforge.tester.open_with_password",
        side_effect=RuntimeError("disk full"),
    )
    with pytest.raises(RuntimeError, match="Unexpected tester error"):
        try_password("test.7z", "pass")


def test_detect_format_by_extension(tmp_path):
    """Extension-based detection (fast path)."""
    for ext, expected in [
        (".zip", "zip"),
        (".rar", "rar"),
        (".7z", "7z"),
        (".pdf", "pdf"),
        (".docx", "office"),
        (".xlsx", "office"),
        (".tar", "tar"),
    ]:
        f = tmp_path / f"archive{ext}"
        f.touch()
        assert detect_format(str(f)) == expected


def test_detect_format_magic_bytes(tmp_path):
    """Magic-byte fallback when extension is ambiguous."""
    f = tmp_path / "unknown.bin"
    f.write_bytes(b"PK\x03\x04")  # ZIP magic
    assert detect_format(str(f)) == "zip"


def test_extract_hash(mocker):
    """extract_hash spawns the correct *2john tool and writes .hash file."""
    mock_run = mocker.patch("hintforge.handlers.subprocess.run")
    mock_run.return_value = MagicMock(
        stdout="hash:deadbeef1234\n", stderr="", returncode=0
    )
    mock_open = mocker.patch("builtins.open", mocker.mock_open())

    hash_file = extract_hash("protected.rar")

    assert Path(hash_file).suffix == ".hash"
    mock_run.assert_called_once()
    mock_open.assert_called_once()


@pytest.mark.skipif(
    not _HAS_MSOFFCRYPTO,
    reason="msoffcrypto not available on Python 3.12+ (see pyproject.toml extras)",
)
def test_office_open_with_password(mocker):
    """Office documents are handled when msoffcrypto is present."""
    mock_office = mocker.MagicMock()
    mocker.patch("hintforge.handlers.msoffcrypto", mock_office)
    mocker.patch("hintforge.handlers.open", mocker.mock_open())

    mock_office.OfficeFile.return_value.is_encrypted.return_value = True
    mock_office.OfficeFile.return_value.load_key = MagicMock()
    mock_office.DecryptionError = Exception

    with open_with_password("secret.docx", "pass123", forced_format="office"):
        pass

    mock_office.OfficeFile.return_value.load_key.assert_called_once_with(
        password="pass123"
    )


def test_office_raises_when_unavailable(mocker):
    """Clear error when office support is missing (e.g. on 3.12)."""
    mocker.patch("hintforge.handlers._HAS_MSOFFCRYPTO", False)
    with pytest.raises(RuntimeError, match="msoffcrypto package"):
        with open_with_password("doc.docx", "pass", forced_format="office"):
            pass  # pragma: no cover


def test_password_error_inheritance():
    """PasswordError is a ValueError for easy catching."""
    err = PasswordError("test")
    assert isinstance(err, ValueError)
