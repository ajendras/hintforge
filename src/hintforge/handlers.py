"""Format handlers for HintForge.

Robust format detection via extension and magic bytes.
Context manager for opening archives with a password (non-destructive).
Supports ZIP, RAR, 7z, PDF, TAR and Office (docx/xlsx via optional msoffcrypto).
Raises clear errors on bad passwords.
"""

from __future__ import annotations

import contextlib
import subprocess
import tarfile
import zipfile
from pathlib import Path
from shutil import which
from typing import Any, Iterator

import pikepdf
import py7zr
import rarfile

# msoffcrypto is provided by the optional 'office' extra
# (no compatible release for Python 3.12+ yet)
try:
    import msoffcrypto
    from msoffcrypto.exceptions import DecryptionError
    _HAS_MSOFFCRYPTO = True
except ImportError:
    msoffcrypto = None  # type: ignore[assignment]
    DecryptionError = Exception  # type: ignore[assignment]
    _HAS_MSOFFCRYPTO = False


class PasswordError(ValueError):
    """Raised when an incorrect password is supplied to an encrypted archive."""


def detect_format(archive_path: str) -> str:
    """Detect archive format using file extension first, then magic bytes.

    Extension check is done even if file does not exist (useful for tests
    and when only filename is known). Magic bytes are used only when the
    file exists.
    """
    path = Path(archive_path)
    ext = path.suffix.lower().strip()

    if ext in (".zip", ".zipx"):
        return "zip"
    if ext in (".rar", ".r00", ".r01"):
        return "rar"
    if ext in (".7z", ".7zip"):
        return "7z"
    if ext == ".pdf":
        return "pdf"
    if ext in (".tar", ".tar.gz", ".tgz", ".gz"):
        return "tar"
    if ext in (".docx", ".xlsx", ".doc", ".xls"):
        return "office"

    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    # magic bytes fallback when file exists
    try:
        import magic  # python-magic
        mime = magic.from_file(str(path), mime=True)
        if "zip" in mime:
            return "zip"
        if "rar" in mime:
            return "rar"
        if "pdf" in mime:
            return "pdf"
        if "7z" in mime.lower() or "7-zip" in mime.lower():
            return "7z"
    except Exception:
        pass

    if ext:
        return ext[1:]
    raise ValueError(f"Could not detect format for {archive_path}")


@contextlib.contextmanager
def open_with_password(
    archive_path: str, password: str, forced_format: str | None = None
) -> Iterator[Any]:
    """Context manager that opens archive with given password.

    On success yields the open archive object.
    On password error raises PasswordError.
    Non-destructive.
    """
    fmt = forced_format or detect_format(archive_path)
    pwd_bytes = password.encode("utf-8", errors="replace")
    try:
        if fmt == "zip":
            with zipfile.ZipFile(archive_path) as zf:
                first = zf.infolist()[0]
                zf.read(first, pwd=pwd_bytes)
                yield zf
        elif fmt == "rar":
            rarfile.UNRAR_TOOL = which("unrar") or "unrar"
            with rarfile.RarFile(archive_path) as rf:
                rf.setpassword(password)
                rf.testrar()
                yield rf
        elif fmt == "pdf":
            with pikepdf.open(archive_path, password=password) as pdf:
                _ = len(pdf.pages)
                yield pdf
        elif fmt == "7z":
            with py7zr.SevenZipFile(archive_path, password=password) as sz:
                sz.testzip()
                yield sz
        elif fmt == "tar":
            mode = "r:gz" if str(archive_path).endswith((".gz", ".tgz")) else "r"
            with tarfile.open(archive_path, mode) as tf:
                yield tf
        elif fmt == "office" and _HAS_MSOFFCRYPTO and msoffcrypto is not None:
            with open(archive_path, "rb") as f:
                office_file = msoffcrypto.OfficeFile(f)
                if office_file.is_encrypted():
                    decrypted = msoffcrypto.io.BytesIO()
                    office_file.load_key(password)
                    office_file.decrypt(decrypted)
                    yield decrypted
                else:
                    yield f
        else:
            raise ValueError(f"Unsupported format: {fmt}")
    except (
        RuntimeError,
        zipfile.BadZipFile,
        rarfile.BadRarFile,
        pikepdf.PasswordError,
        py7zr.Bad7zFile,
        DecryptionError,
        ValueError,
    ) as exc:
        msg = str(exc).lower()
        if "password" in msg or "bad" in msg or isinstance(exc, pikepdf.PasswordError):
            raise PasswordError(f"Incorrect password for {fmt.upper()} archive") from exc
        raise


def extract_hash(archive_path: str, forced_format: str | None = None) -> str | None:
    """Extract hash for hashcat using john *2john tools if available."""
    fmt = forced_format or detect_format(archive_path)
    if fmt == "zip":
        try:
            out = subprocess.check_output(
                ["zip2john", archive_path], stderr=subprocess.DEVNULL, text=True
            )
            return out.strip().split(":")[0]
        except Exception:
            return None
    return None
