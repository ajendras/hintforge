"""Password tester facade for HintForge.

Provides a clean try_password() entry point that delegates to the
format-specific logic in handlers.py (open_with_password + PasswordError).
Non-destructive, safe for use in dry-run, strategies and live recovery.
"""

from __future__ import annotations

from .handlers import open_with_password, PasswordError


def try_password(
    archive_path: str, password: str, forced_format: str | None = None
) -> bool:
    """Test a candidate password against an encrypted archive.

    Uses the unified open_with_password context manager (which performs
    the minimal work necessary to validate the password for each format).
    Returns True on success, False on PasswordError (wrong password).
    All other exceptions are propagated so the orchestrator can surface them.

    This function is the single source of truth used by core.recover(),
    HashcatStrategy, the web dashboard jobs, and all tests.
    """
    try:
        with open_with_password(
            archive_path, password, forced_format=forced_format
        ):
            return True
    except PasswordError:
        return False
    except Exception as exc:
        raise RuntimeError(
            f"Unexpected tester error on {archive_path}"
        ) from exc


__all__ = ["try_password"]
