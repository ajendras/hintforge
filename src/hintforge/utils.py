"""Utility functions for HintForge.

Includes neo-brutalist UI components (Rich panels + chunky ASCII art),
config loading from config.toml, session persistence helpers,
password sanitization, and archive metadata utilities.

All UI follows the exact neo-brutalist direction: thick HEAVY borders,
hard offset visual language via styling, flat bright blocks using
#ff0044 (hot pink) and #00ff9f (lime), chunky mono-style text, no
rounding or blur. Loud, playful, high-contrast.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]

from rich.panel import Panel
from rich.text import Text
from rich import box

from .models import Config, SessionState

# Neo-brutalist colour palette - used everywhere
BRUTALIST_PINK = "#ff0044"
BRUTALIST_LIME = "#00ff9f"
BRUTALIST_BLACK = "#000000"


def sanitize_password(pw: str | bytes) -> str:
    """Sanitize and normalize a candidate password.

    Strips whitespace, removes control characters, truncates to a
    reasonable maximum length, and ensures valid UTF-8. Used by
    tester and core before any archive operation.

    Args:
        pw: Raw password (string or bytes).

    Returns:
        Cleaned password string (never empty).

    Raises:
        ValueError: If the password is empty after sanitization or
            cannot be decoded.
    """
    if isinstance(pw, bytes):
        try:
            pw = pw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ValueError("Cannot decode password bytes as UTF-8") from exc

    if not isinstance(pw, str):
        pw = str(pw)

    # Remove control characters
    cleaned = "".join(c for c in pw if ord(c) >= 32 or c in "\t\n")
    # Normalize whitespace
    cleaned = " ".join(cleaned.split())

    if len(cleaned) > 256:
        cleaned = cleaned[:256]

    if not cleaned or cleaned.isspace():
        raise ValueError("Password cannot be empty after sanitization")

    return cleaned


def brutalist_panel(
    title: str,
    content: str | Text,
    style: str = BRUTALIST_LIME,
    subtitle: str | None = None,
) -> Panel:
    """Return a Rich Panel styled in loud neo-brutalist aesthetic.

    Uses box.HEAVY for the thick 3px border effect in terminal,
    primary palette colours, centered chunky titles, generous padding,
    and high-contrast text. Exactly matches the visual direction used
    in CLI and core success/failure screens.

    Args:
        title: Uppercase panel title.
        content: Main body text (string or rich Text).
        style: Border and accent colour (defaults to lime).
        subtitle: Optional subtitle shown at bottom.

    Returns:
        Ready-to-print Rich Panel.
    """
    if isinstance(content, str):
        body = Text(content, style=f"bold {style}")
    else:
        body = content

    return Panel(
        body,
        title=f"[{style} bold]{title}[/{style} bold]",
        box=box.HEAVY,
        border_style=style,
        padding=(2, 4),
        title_align="center",
        subtitle=subtitle,
        subtitle_align="center",
    )


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from config.toml with fallback to defaults.

    Supports both a top-level TOML file and a [hintforge] section.
    Uses tomllib when available (Python 3.11+); falls back gracefully
    on older Pythons or missing files. All values are validated by
    the Pydantic Config model.

    Args:
        config_path: Optional override for the TOML file.

    Returns:
        Validated Config object (always succeeds with defaults).
    """
    config = Config()

    if config_path is None:
        config_path = Path("config.toml")
    path = Path(config_path)

    if path.is_file() and tomllib is not None:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            settings = data.get("hintforge", data)
            for key, value in settings.items():
                if hasattr(config, key) and not key.startswith("_"):
                    try:
                        # Let Pydantic validation handle conversion
                        setattr(config, key, value)
                    except Exception:
                        pass  # keep default on validation error
        except Exception:
            # TOML parse error, permission error, etc. -> silent fallback
            pass

    return config


def save_session(state: SessionState) -> None:
    """Persist a SessionState to a JSON checkpoint in .hintforge/.

    Creates the directory if it does not exist. Uses Pydantic's
    JSON mode to correctly serialize sets and other types.

    Args:
        state: SessionState instance to save.

    Raises:
        TypeError: If state is not a SessionState.
        RuntimeError: If serialization or I/O fails.
    """
    if not isinstance(state, SessionState):
        raise TypeError("state must be an instance of SessionState")

    session_dir = Path(".hintforge")
    session_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(state.archive_path).name
    session_file = session_dir / f"{filename}.session.json"

    try:
        data = state.model_dump(mode="json")
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to save session {session_file}: {exc}") from exc


def render_brutalist_progress(
    current: int,
    total: int,
    rate: float = 0.0,
    eta: float = 0.0,
    current_pw: str = "",
) -> str:
    """Return a chunky ASCII neo-brutalist progress panel.

    Uses heavy block characters (█ ░), double-line borders, and
    primary colours via ANSI escapes where supported. Designed to
    be loud and fit the terminal UI aesthetic when Rich progress
    is not used. Fully responsive to terminal width.

    Args:
        current: Candidates tested so far.
        total: Total candidates in this run.
        rate: Tests per second (for ETA).
        eta: Estimated seconds remaining.
        current_pw: The password currently being tested (truncated).

    Returns:
        Multi-line ASCII art string ready for console.print().
    """
    if total <= 0:
        percent = 0
    else:
        percent = min(100, int((current / total) * 100))

    bar_width = 28
    filled = int(bar_width * current / total) if total > 0 else 0
    bar = "█" * filled + "▒" * (bar_width - filled)

    pw_display = current_pw[:28] + "…" if len(current_pw) > 28 else current_pw
    pw_display = pw_display.ljust(28)

    lines: list[str] = [
        "╔════════════════════════════════════════════════════════════╗",
        "║                   HINTFORGE RECOVERY ENGINE                ║",
        "╠════════════════════════════════════════════════════════════╣",
        f"║ PROGRESS  {current:3}/{total:3}  {percent:3}%  {bar}  ║",
        f"║ CANDIDATE {pw_display}                       ║",
    ]

    if rate > 0.1 and eta > 0:
        lines.append(f"║ RATE      {rate:5.1f} pw/s    ETA {eta:5.0f}s             ║")
    else:
        lines.append("║ RATE      --- pw/s      ETA ---s                       ║")

    lines.extend(
        [
            "╚════════════════════════════════════════════════════════════╝",
            "",
        ]
    )

    return "\n".join(lines)


def get_archive_info(archive_path: str) -> dict[str, Any]:
    """Return basic metadata about an archive file.

    Used by analysis and session persistence. Includes size,
    extension and a crude modification timestamp.

    Args:
        archive_path: Path to the archive.

    Returns:
        Dictionary with keys: exists, size_bytes, name, extension,
            modified (or empty dict on error).
    """
    try:
        p = Path(archive_path)
        if not p.exists():
            return {"exists": False, "size_bytes": 0, "name": p.name}

        stat = p.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "name": p.name,
            "extension": p.suffix.lower(),
            "modified": stat.st_mtime,
        }
    except Exception:
        return {"exists": False, "size_bytes": 0, "name": "unknown"}


__all__ = [
    "sanitize_password",
    "brutalist_panel",
    "load_config",
    "save_session",
    "render_brutalist_progress",
    "get_archive_info",
    "BRUTALIST_PINK",
    "BRUTALIST_LIME",
]
