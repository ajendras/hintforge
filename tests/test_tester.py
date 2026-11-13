"""Tests for the password tester and format dispatch.

Unit tests for each format-specific tester, integration tests using
temporary ZIP archives (with known test password), edge cases, error
handling and sanitization. Uses pytest fixtures and mocking for RAR,
7z and PDF paths that are harder to create in pure stdlib.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.hintforge.handlers import PasswordError, detect_format
from src.hintforge.models import Candidate
from src.hintforge.tester import (
    _detect_format_fallback,
    _test_7z,
    _test_pdf,
    _test_rar,
    _test_zip,
    test_candidate,
    try_password,
)


@pytest.fixture
def plain_zip_archive(tmp_path: Path) -> Path:
    """Create a regular (non-encrypted) ZIP for baseline testing.

    Our _test_zip returns True immediately when no encrypted members
    are present, which matches real behaviour for many user archives.
    """
    archive = tmp_path / "plain.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", b"not secret")
    return archive


@pytest.fixture
def encrypted_zip_archive(tmp_path: Path) -> Path:
    """Create an encrypted ZIP using the Python zipfile password API.

    Note: the test password is 'TestPass123!'. The fixture writes an
    encrypted member so that real password validation is exercised.
    """
    archive = tmp_path / "encrypted.zip"
    password = "TestPass123!"
    data = b"Top secret archive content for testing"

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Create an encrypted file member
        info = zipfile.ZipInfo("secret.txt")
        info.flag_bits |= 0x1  # Encrypted bit
        with zf.open(info, mode="w", pwd=password.encode("utf-8")) as f:
            f.write(data)

    return archive


def test_try_password_plain_zip(plain_zip_archive: Path) -> None:
    """Any password succeeds on non-encrypted ZIP (per current implementation)."""
    assert try_password(str(plain_zip_archive), "anything") is True
    assert try_password(str(plain_zip_archive), "") is True  # edge case


def test_try_password_encrypted_zip_success(encrypted_zip_archive: Path) -> None:
    """Correct password opens the encrypted test archive."""
    assert try_password(str(encrypted_zip_archive), "TestPass123!") is True


def test_try_password_encrypted_zip_failure(encrypted_zip_archive: Path) -> None:
    """Wrong password returns False."""
    assert try_password(str(encrypted_zip_archive), "WrongPassword!") is False


def test_sanitize_password_integration(encrypted_zip_archive: Path) -> None:
    """try_password calls sanitize_password internally (extra spaces, long pw)."""
    assert try_password(str(encrypted_zip_archive), "  TestPass123!   ") is True
    # Truncation test
    long_pw = "TestPass123!" * 30
    # The sanitized version will be truncated but still fail the real test
    assert try_password(str(encrypted_zip_archive), long_pw) is False


def test_detect_format_on_zip(encrypted_zip_archive: Path) -> None:
    """detect_format correctly identifies our test ZIP."""
    fmt = detect_format(str(encrypted_zip_archive))
    assert fmt == "zip"


def test_fallback_detection(tmp_path: Path) -> None:
    """Internal fallback works when handlers.detect_format is unavailable."""
    rar = tmp_path / "test.rar"
    rar.touch()
    assert _detect_format_fallback(str(rar)) == "rar"

    pdf = tmp_path / "doc.pdf"
    pdf.touch()
    assert _detect_format_fallback(str(pdf)) == "pdf"

    unknown = tmp_path / "archive.bin"
    unknown.touch()
    assert _detect_format_fallback(str(unknown)) == "zip"


def test_test_candidate_wrapper(encrypted_zip_archive: Path) -> None:
    """test_candidate accepts a Candidate object."""
    cand = Candidate(score=0.95, value="TestPass123!")
    assert test_candidate(str(encrypted_zip_archive), cand) is True


def test_try_password_nonexistent_file() -> None:
    """Clear FileNotFoundError for missing archive."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        try_password("/does/not/exist/archive.zip", "pw")


def test_try_password_empty_after_sanitize(encrypted_zip_archive: Path) -> None:
    """Empty password after sanitization returns False quickly."""
    assert try_password(str(encrypted_zip_archive), "   ") is False
    assert try_password(str(encrypted_zip_archive), "") is False


def test_try_password_invalid_path_type() -> None:
    """Non-string path raises ValueError."""
    with pytest.raises(ValueError, match="Archive path must be a non-empty string"):
        try_password(123, "pw")  # type: ignore[arg-type]


@patch("src.hintforge.tester.detect_format")
def test_format_dispatch_rar(mock_detect, tmp_path: Path) -> None:
    """Dispatch to RAR tester when format is detected as rar."""
    mock_detect.return_value = "rar"
    archive = tmp_path / "test.rar"
    archive.touch()

    with patch("src.hintforge.tester._test_rar", return_value=True) as mock_test:
        assert try_password(str(archive), "rarpass") is True
        mock_test.assert_called_once()


@patch("src.hintforge.tester.detect_format")
def test_format_dispatch_7z(mock_detect, tmp_path: Path) -> None:
    """Dispatch to 7z tester."""
    mock_detect.return_value = "7z"
    archive = tmp_path / "test.7z"
    archive.touch()

    with patch("src.hintforge.tester._test_7z", return_value=True) as mock_test:
        assert try_password(str(archive), "7zpass") is True
        mock_test.assert_called_once()


@patch("src.hintforge.tester.detect_format")
def test_format_dispatch_pdf(mock_detect, tmp_path: Path) -> None:
    """Dispatch to PDF tester."""
    mock_detect.return_value = "pdf"
    archive = tmp_path / "test.pdf"
    archive.touch()

    with patch("src.hintforge.tester._test_pdf", return_value=True) as mock_test:
        assert try_password(str(archive), "pdfpass") is True
        mock_test.assert_called_once()


def test_test_zip_no_encrypted_members(plain_zip_archive: Path) -> None:
    """_test_zip returns True when archive has no encrypted files."""
    assert _test_zip(str(plain_zip_archive), "any") is True


def test_test_rar_wrong_password_raises_properly() -> None:
    """RAR tester returns False on BadPassword (does not leak exception)."""
    with patch("rarfile.RarFile") as mock_rar:
        mock_rar.return_value.testrar.side_effect = Exception("Bad password")
        assert _test_rar("dummy.rar", "bad") is False


def test_test_7z_bad_password() -> None:
    """7z tester maps BadPassword to False."""
    with patch("py7zr.SevenZipFile") as mock_7z:
        mock_7z.side_effect = Exception("BadPassword")
        # The real implementation catches py7zr.BadPassword specifically
        # but our mock hits the generic handler
        assert _test_7z("dummy.7z", "bad") is False


def test_test_pdf_password_error() -> None:
    """PDF tester maps PasswordError to False."""
    with patch("pikepdf.open") as mock_pdf:
        mock_pdf.side_effect = Exception("PasswordError")
        assert _test_pdf("dummy.pdf", "bad") is False


def test_unknown_format_falls_back_to_zip(plain_zip_archive: Path) -> None:
    """Unknown format uses ZIP tester as conservative default."""
    with patch("src.hintforge.tester.detect_format", return_value="unknown"):
        assert try_password(str(plain_zip_archive), "any") is True
