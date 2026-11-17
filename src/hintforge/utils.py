"""Utility functions for HintForge.

Includes config loading, session persistence, neo-brutalist UI helpers,
hashcat runner and job persistence for the web dashboard.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

import tomllib
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from .models import Config, Job, SessionState


console = Console(highlight=False, color_system="truecolor")


def load_config() -> Config:
    """Load configuration from config.toml or return defaults."""
    config = Config()
    config_path = Path("config.toml")
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        except Exception:  # pragma: no cover
            pass  # fall back to defaults
    return config


def save_session(state: SessionState) -> None:
    """Save session state as JSON for resumability."""
    session_dir = Path(".hintforge")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{Path(state.archive_path).name}.session.json"
    try:
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
    except Exception:  # pragma: no cover
        console.print("[dim]Could not save session.[/]")


def save_job(job: Job) -> None:
    """Persist a Job object to the .hintforge directory."""
    jobs_dir = Path(".hintforge")
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_file = jobs_dir / f"job-{job.id}.json"
    try:
        with open(job_file, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))
    except Exception:  # pragma: no cover
        pass


def load_jobs() -> list[Job]:
    """Load all jobs from disk (used by dashboard)."""
    jobs_dir = Path(".hintforge")
    loaded: list[Job] = []
    if not jobs_dir.exists():
        return loaded
    for job_file in jobs_dir.glob("job-*.json"):
        try:
            with open(job_file, encoding="utf-8") as f:
                data = json.load(f)
            job = Job.model_validate(data)
            loaded.append(job)
        except Exception:
            continue
    return sorted(loaded, key=lambda j: j.created_at, reverse=True)


def brutalist_panel(title: str, content: Any, style: str = "#00ff9f") -> Panel:
    """Create a chunky neo-brutalist Rich panel matching the CLI aesthetic."""
    text = Text(str(content), style=style)
    return Panel(
        text,
        title=f"[bold #ff0044]{title}[/]",
        box=box.HEAVY,
        border_style="#ff0044",
        padding=(1, 4),
        title_align="left",
    )


def sanitize_password(pw: str) -> str:
    """Sanitize password for safe display (used in UI)."""
    if not pw or len(pw) < 4:
        return pw
    return pw[:4] + "●" * (len(pw) - 4)


def is_hashcat_available() -> bool:
    """Check if hashcat binary is available in PATH."""
    return which("hashcat") is not None


def run_hashcat(
    hash_file: str,
    mode: int,
    attack_mode: int = 3,
    mask: str | None = None,
    rules_file: str | None = None,
    config: Config | None = None,
) -> str | None:
    """Execute hashcat and parse first cracked candidate.

    Returns the first password found or None.
    """
    config = config or Config()
    cmd = [
        config.hashcat_path,
        "--quiet",
        "-m",
        str(mode),
        "-a",
        str(attack_mode),
        hash_file,
    ]
    if mask and attack_mode == 3:
        cmd.append(mask)
    if rules_file and attack_mode == 0 and rules_file:
        cmd.extend(["-r", rules_file])
    if config.use_gpu:
        cmd.extend(["-D", "2"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        for line in lines:
            if ":" in line:
                return line.split(":", 1)[-1].strip()
        if lines:
            return lines[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return None


__all__ = [
    "load_config",
    "save_session",
    "save_job",
    "load_jobs",
    "brutalist_panel",
    "sanitize_password",
    "is_hashcat_available",
    "run_hashcat",
]
