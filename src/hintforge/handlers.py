"""Format handlers for HintForge.

Robust format detection via extension and magic bytes.
Context manager for opening archives with a password (non-destructive).
Supports ZIP, RAR, 7z, PDF, TAR and Office (docx/xlsx via msoffcrypto).
Raises clear errors on bad passwords.
"""

from __future__ import annotations

import contextlib
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Iterator

import msoffcrypto
import pikepdf
import py7zr
import rarfile
from msoffcrypto.exceptions import DecryptionError


class PasswordError(ValueError):
    """Raised when an incorrect password is supplied to an encrypted archive."""


def detect_format(archive_path: str) -> str:
    """Detect archive format using file extension first, then magic bytes.

    Supports: zip, rar, 7z, pdf, tar, office (docx/xlsx). Falls back to 'zip'
    for unknown files. Office documents are detected before ZIP because modern
    Office files are ZIP-based containers.

    Args:
        archive_path: Path to the archive file.

    Returns:
        Lowercase format identifier.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(archive_path)
    if not path.is_file():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    suffix = path.suffix.lower()

    # Fast extension mapping (office before zip)
    ext_map = {
        ".docx": "office",
        ".xlsx": "office",
        ".docm": "office",
        ".xlsm": "office",
        ".pptx": "office",
        ".zip": "zip",
        ".jar": "zip",
        ".war": "zip",
        ".rar": "rar",
        ".7z": "7z",
        ".7zip": "7z",
        ".pdf": "pdf",
        ".tar": "tar",
        ".tgz": "tar",
        ".tar.gz": "tar",
        ".tbz": "tar",
        ".tar.bz2": "tar",
        ".txz": "tar",
    }
    if suffix in ext_map:
        return ext_map[suffix]

    # Magic header inspection
    try:
        header = path.read_bytes()[:32]
        if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):
            return "zip"
        if header.startswith(b"Rar!") or header[0:4] == b"\x52\x61\x72\x21":
            return "rar"
        if header.startswith(b"%PDF"):
            return "pdf"
        if header.startswith(b"7z\xBC\xAF\x27\x1C"):
            return "7z"
        if header[257:265] == b"ustar\x00" or b"ustar" in header:
            return "tar"
    except OSError:
        pass

    # Optional python-magic for deeper inspection
    try:
        import magic  # type: ignore[import-not-found]

        mime = magic.from_file(str(path), mime=True).lower()
        if "zip" in mime or "application/zip" in mime:
            return "zip"
        if "rar" in mime:
            return "rar"
        if "pdf" in mime:
            return "pdf"
        if "7z" in mime or "x-7z-compressed" in mime:
            return "7z"
        if "ms-office" in mime or "officedocument" in mime:
            return "office"
    except (ImportError, OSError, Exception):
        pass

    return "zip"  # conservative default for unknown archives


@contextlib.contextmanager
def open_with_password(
    archive_path: str, password: str, forced_format: str | None = None
) -> Iterator[Any]:
    """Context manager to open an encrypted archive with a password.

    Yields a ready-to-use archive object (ZipFile, RarFile, SevenZipFile,
    Pdf object, TarFile or msoffcrypto OfficeFile). Automatically tests
    the password on encrypted members. Never modifies the original file.

    Args:
        archive_path: Path to archive.
        password: Password to use.
        forced_format: Override auto-detection.

    Yields:
        Archive handler object.

    Raises:
        PasswordError: If password is incorrect.
        FileNotFoundError, RuntimeError: For other I/O or format errors.
    """
    fmt = forced_format or detect_format(archive_path)
    pw = password.strip()

    try:
        if fmt == "zip":
            with zipfile.ZipFile(archive_path) as zf:
                # Test encrypted members if present
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # encrypted bit
                        zf.read(info.filename, pwd=pw.encode("utf-8", errors="replace"))
                        break
                yield zf

        elif fmt == "rar":
            rf = rarfile.RarFile(archive_path)
            rf.set_password(pw)
            rf.testrar()  # explicit password validation
            try:
                yield rf
            finally:
                rf.close()

        elif fmt == "7z":
            with py7zr.SevenZipFile(
                archive_path, mode="r", password=pw
            ) as archive:
                archive.list()  # forces decryption check
                yield archive

        elif fmt == "pdf":
            with pikepdf.open(
                archive_path,
                password=pw,
                allow_overwriting_input=False,
            ) as pdf:
                # Force light parsing to confirm password worked
                if pdf.pages:
                    _ = len(pdf.pages)
                yield pdf

        elif fmt == "tar":
            # Native tar has no password support; open as regular tarfile.
            # Real encrypted TARs are usually inside another container.
            with tarfile.open(archive_path) as tf:
                yield tf

        elif fmt == "office":
            with open(archive_path, "rb") as f:
                office = msoffcrypto.OfficeFile(f)
                if office.is_encrypted():
                    office.load_key(password=pw)
                    # Validate by decrypting to a discarding sink (no full
                    # in-memory copy of the document)
                    class _Sink:
                        def write(self, data: bytes) -> int:
                            return len(data)

                    office.decrypt(_Sink())
                yield office

        else:
            # Unknown fallback to ZIP
            with zipfile.ZipFile(archive_path) as zf:
                yield zf

    except (
        rarfile.BadRarFile,
        rarfile.RarWrongPassword,
        py7zr.BadPassword,
        pikepdf.PasswordError,
        zipfile.BadZipFile,
        DecryptionError,
        RuntimeError,
    ) as exc:
        raise PasswordError(f"Incorrect password for {fmt.upper()} archive") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to open {archive_path} as {fmt}: {exc}") from exc


__all__ = ["detect_format", "open_with_password", "PasswordError"]
