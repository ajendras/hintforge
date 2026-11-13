"""Password testing facade for HintForge.

Dispatches to format-specific handlers for ZIP, RAR, PDF, 7z and TAR.
Uses non-destructive read/test operations only. Never modifies archives.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pikepdf
import py7zr
import rarfile

from .handlers import detect_format  # planned thin wrapper; we provide robust fallback
from .models import Candidate
from .utils import sanitize_password


def _detect_format_fallback(path: str) -> str:
    """Internal fallback detection when handlers.detect_format is not available."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archive not found: {path}")

    suffix = p.suffix.lower()
    if suffix in (".zip", ".jar"):
        return "zip"
    if suffix == ".rar":
        return "rar"
    if suffix in (".7z", ".7zip"):
        return "7z"
    if suffix == ".pdf":
        return "pdf"
    if any(suffix.startswith(x) for x in (".tar", ".tgz", ".tbz")):
        return "tar"

    # Try python-magic if installed
    try:
        import magic  # type: ignore[import-not-found]

        mime = magic.from_file(str(p.resolve()), mime=True)
        if "zip" in mime or "application/zip" in mime:
            return "zip"
        if "rar" in mime:
            return "rar"
        if "pdf" in mime:
            return "pdf"
    except Exception:  # pragma: no cover - optional dependency
        pass

    return "zip"  # conservative default


def _test_zip(path: str, password: str) -> bool:
    """Test ZIP archive (including AES-encrypted members)."""
    try:
        with zipfile.ZipFile(path) as zf:
            # If no encrypted files, any password is fine but we still validate
            encrypted = any(info.flag_bits & 0x1 for info in zf.infolist())
            if not encrypted:
                return True
            # Test first encrypted file
            for info in zf.infolist():
                if info.flag_bits & 0x1:
                    try:
                        zf.read(info.filename, pwd=password.encode("utf-8", errors="replace"))
                        return True
                    except (RuntimeError, zipfile.BadZipFile, RuntimeError):
                        return False
        return True
    except (zipfile.BadZipFile, RuntimeError, OSError):
        return False
    except Exception:  # pragma: no cover
        return False


def _test_rar(path: str, password: str) -> bool:
    """Test RAR archive using rarfile."""
    try:
        with rarfile.RarFile(path) as rf:
            rf.set_password(password)
            # testrar() will raise on bad password
            rf.testrar()
        return True
    except (rarfile.BadRarFile, rarfile.RarWrongPassword, RuntimeError):
        return False
    except Exception:  # pragma: no cover
        return False


def _test_7z(path: str, password: str) -> bool:
    """Test 7z archive using py7zr."""
    try:
        with py7zr.SevenZipFile(path, mode="r", password=password) as archive:
            archive.list()
        return True
    except py7zr.BadPassword:
        return False
    except Exception:  # pragma: no cover
        return False


def _test_pdf(path: str, password: str) -> bool:
    """Test PDF with pikepdf (handles both 40-bit, 128-bit and AES)."""
    try:
        with pikepdf.open(path, password=password, allow_overwriting_input=False) as pdf:
            # Force a small amount of parsing
            _ = pdf.pages[0] if pdf.pages else None
        return True
    except pikepdf.PasswordError:
        return False
    except Exception as exc:
        if any(term in str(exc).lower() for term in ("password", "incorrect", "invalid")):
            return False
        raise


def _test_tar(path: str, password: str) -> bool:
    """Placeholder for encrypted TAR support.

    Native tar does not support passwords. We assume the archive may be
    a .tar inside a 7z/zip or encrypted with external tools (gpg, openssl).
    Full support will be provided via handlers.py.
    """
    # For now we return False so the pipeline continues with other strategies.
    # In a future extension this could shell out to gpg --decrypt --passphrase ...
    return False


def try_password(path: str, pw: str) -> bool:
    """Attempt to unlock the archive with the supplied password.

    Dispatches to the correct handler based on auto-detected format.
    All operations are read-only and non-destructive.

    Args:
        path: Absolute or relative path to the encrypted archive.
        pw: Candidate password to test.

    Returns:
        True if the password successfully opens the archive.

    Raises:
        FileNotFoundError: If the archive does not exist.
        ValueError: On obviously malformed input.
    """
    if not path or not isinstance(path, str):
        raise ValueError("Archive path must be a non-empty string")

    archive_path = Path(path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive does not exist or is not a file: {path}")

    password = sanitize_password(pw)
    if not password:
        return False

    try:
        fmt = detect_format(str(archive_path))
    except Exception:  # handlers may not be implemented yet
        fmt = _detect_format_fallback(str(archive_path))

    if fmt == "zip":
        return _test_zip(str(archive_path), password)
    if fmt == "rar":
        return _test_rar(str(archive_path), password)
    if fmt == "7z":
        return _test_7z(str(archive_path), password)
    if fmt == "pdf":
        return _test_pdf(str(archive_path), password)
    if fmt == "tar":
        return _test_tar(str(archive_path), password)

    # Unknown format falls back to ZIP test (most common)
    return _test_zip(str(archive_path), password)


def test_candidate(path: str, candidate: Candidate) -> bool:
    """Convenience wrapper for testing a Candidate object."""
    return try_password(path, candidate.value)


__all__ = ["try_password", "test_candidate", "detect_format"]
