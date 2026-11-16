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
import re
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from .models import Config, SessionState

# Neo-brutalist colour palette - used everywhere
BRUTALIST_PINK = "#ff0044"
BRUTALIST_LIME = "#00ff9f"
BRUTALIST_BLACK = "#000000"

console = Console(highlight=False, color_system="truecolor")


def sanitize_password(pw: str | bytes) -> str:
    """Sanitize and normalize a candidate password.

    Strips whitespace, removes control characters, truncates to a
    reasonable maximum length, and ensures valid UTF-8. Used by
    tester, core and hashcat integration to avoid encoding issues.
    """
    if isinstance(pw, bytes):
        pw = pw.decode("utf-8", errors="replace")
    pw = str(pw).strip()
    pw = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", pw)
    return pw[:128]


def load_config() -> Config:
    """Load configuration from config.toml (or defaults)."""
    config_path = Path("config.toml")
    if config_path.exists() and tomllib is not None:
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return Config.model_validate(data)
        except Exception:  # pragma: no cover
            pass
    return Config()


def save_session(state: SessionState) -> None:
    """Persist current recovery state to disk."""
    session_dir = Path(".hintforge")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{Path(state.archive_path).name}.session.json"
    try:
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
    except Exception as exc:  # pragma: no cover
        console.print(f"[dim]Warning: could not save session: {exc}[/]")


def brutalist_panel(title: str, content: Any, style: str = BRUTALIST_LIME) -> Panel:
    """Create a chunky neo-brutalist Rich panel with heavy borders."""
    if not isinstance(content, Text):
        content = Text(str(content), style=style)
    return Panel(
        content,
        title=Text(title.upper(), style="bold white"),
        box=box.HEAVY,
        border_style=BRUTALIST_PINK,
        padding=(1, 3),
        title_align="center",
    )


def is_hashcat_available() -> bool:
    """Return True if the hashcat binary is available in PATH."""
    return which("hashcat") is not None


def run_hashcat(
    hash_file: str,
    mode: int,
    attack_mode: int = 3,
    mask: str | None = None,
    rules_file: str | None = None,
    config: Config | None = None,
) -> str | None:
    """Execute hashcat with the supplied parameters and parse the potfile.

    Returns the first cracked password (if any) or None. Uses a short
    timeout so the main pipeline is not blocked. GPU is preferred when
    configured.
    """
    if config is None:
        config = Config()
    hc_bin = which("hashcat")
    if not hc_bin:
        return None
    potfile = Path(".hintforge") / "hashcat.potfile"
    potfile.parent.mkdir(parents=True, exist_ok=True)
    if potfile.exists():
        potfile.unlink(missing_ok=True)

    cmd: list[str] = [
        hc_bin,
        "-m",
        str(mode),
        "-a",
        str(attack_mode),
        "--potfile-path",
        str(potfile),
        "--quiet",
        "--session",
        "hintforge",
    ]
    if config.use_gpu:
        cmd.extend(["-D", "2", "--force"])
    if mask and attack_mode in (3, 6):
        cmd.append(mask)
    if rules_file and attack_mode == 0:
        cmd.extend(["-r", rules_file])
    cmd.append(hash_file)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if potfile.exists():
            with open(potfile, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if ":" in line:
                        password = line.split(":", 1)[1].strip()
                        if password:
                            return sanitize_password(password)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return None
