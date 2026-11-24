"""Recovery orchestrator for HintForge.

Coordinates the Context Oracle, pluggable attack strategies, password tester,
session persistence and live neo-brutalist progress reporting.

Now includes export_session() / import_session() for sharing recovery state.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from .models import Candidate, Config, SessionState, Job, StrengthReport
from .oracle import generate_candidates
from .strategies import run_strategy
from .tester import try_password
from .utils import (
    brutalist_panel,
    is_hashcat_available,
    load_config,
    load_jobs,
    save_job,
    save_session,
    sanitize_password,
)

console = Console(highlight=False, color_system="truecolor")


def _load_or_create_session(
    archive_path: str, hint: str, max_candidates: int, resume: bool
) -> SessionState:
    """Load existing session or create a fresh one."""
    session_file = Path(".hintforge") / f"{Path(archive_path).name}.session.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    if resume and session_file.exists():
        try:
            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)
            state = SessionState.model_validate(data)
            console.print("[#00ff9f]Resuming previous session...[/]")
            return state
        except Exception as exc:  # pragma: no cover
            console.print(f"[#ff0044]Session load failed, starting fresh: {exc}[/]")

    return SessionState(
        archive_path=archive_path,
        hint=hint,
        candidates_tested=0,
        total_candidates=max_candidates,
        tested=set(),
        found=None,
        start_time=time.time(),
    )


def _save_session(state: SessionState) -> None:
    """Persist current recovery state to disk."""
    try:
        save_session(state)
    except Exception as exc:  # pragma: no cover
        console.print(f"[dim]Warning: could not save session: {exc}[/]")


def _humanize_time(seconds: float) -> str:
    """Convert seconds into a human-readable crack-time string."""
    if seconds < 1:
        return "< 1 second"
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    if seconds < 3600:
        return f"{seconds / 60:.0f} minutes"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} hours"
    if seconds < 2_592_000:
        return f"{seconds / 86400:.0f} days"
    if seconds < 31_536_000:
        return f"{seconds / 2_592_000:.0f} months"
    years = seconds / 31_536_000
    if years < 100:
        return f"{years:.0f} years"
    return "centuries"


def estimate_strength(password: str, config: Config | None = None) -> StrengthReport:
    """Built-in password strength estimator with crack-time projection.

    Calculates entropy from character pool size, penalises common patterns,
    and projects crack time for online, CPU-offline and GPU-offline scenarios
    using the speeds defined in Config. Returns a StrengthReport model.
    """
    if not password or not isinstance(password, str):
        return StrengthReport(
            password="",
            entropy_bits=0.0,
            crack_times={},
            strength="invalid",
            feedback=["Password must be a non-empty string."],
        )

    if config is None:
        config = load_config()

    length = len(password)
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    pool = 0
    if has_lower:
        pool += 26
    if has_upper:
        pool += 26
    if has_digit:
        pool += 10
    if has_special:
        pool += 32
    if pool == 0:
        pool = 10

    entropy = length * math.log2(pool)

    lower_pw = password.lower()
    common = [
        "password",
        "123456",
        "qwerty",
        "abc123",
        "letmein",
        "admin",
        "welcome",
        "monkey",
        "dog",
        "max",
        "2020",
        "2023",
        "vacation",
        "birth",
        "name",
        "pet",
        "family",
    ]
    if any(word in lower_pw for word in common):
        entropy *= 0.4
    if password.isnumeric() or (password.isalpha() and len(password) >= 6) or password == password[::-1]:
        entropy *= 0.65

    entropy = round(min(max(entropy, 0.0), 140.0), 2)

    speeds = {
        "online": config.online_guesses_per_second,
        "cpu_offline": config.cpu_guesses_per_second,
        "gpu_offline": config.gpu_guesses_per_second,
    }

    crack_times = {}
    for name, speed in speeds.items():
        # conservative full keyspace (realistic average is ~50%)
        seconds = (2**entropy) / speed if entropy > 0 else 0.0
        crack_times[name] = _humanize_time(seconds)

    if entropy < 30:
        strength = "very weak"
        feedback = [
            "Extremely easy to guess or brute-force.",
            "Never use this for important archives.",
        ]
    elif entropy < 50:
        strength = "weak"
        feedback = ["Still vulnerable to dictionary + rule attacks."]
    elif entropy < 70:
        strength = "moderate"
        feedback = ["Acceptable for low-value data."]
    elif entropy < 100:
        strength = "strong"
        feedback = ["Good resistance against offline attacks."]
    else:
        strength = "very strong"
        feedback = ["Extremely difficult to crack with current hardware."]

    if length < 12:
        feedback.append("Increase length to at least 16 characters.")
    if not (has_lower and has_upper and has_digit and has_special):
        feedback.append("Mix uppercase, lowercase, numbers and symbols.")
    if any(word in lower_pw for word in ["birth", "name", "dog", "cat", "year", "202"]):
        feedback.append("Avoid personal information and predictable patterns.")

    return StrengthReport(
        password=password,
        entropy_bits=entropy,
        crack_times=crack_times,
        strength=strength,
        feedback=feedback,
    )


def analyze(archive_path: str, forced_format: str | None = None) -> dict[str, Any]:
    """Analyze encryption strength of an archive and recommend an attack strategy.

    Uses file magic/extension and basic header inspection. Returns a report
    compatible with the CLI analysis table. Now includes Office (docx/xlsx)
    and hashcat availability.
    """
    if not Path(archive_path).exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    from .handlers import detect_format

    fmt = forced_format or detect_format(archive_path)
    size_mb = Path(archive_path).stat().st_size / (1024 * 1024)

    strength_map = {
        "zip": 6.5,
        "rar": 8.2,
        "7z": 9.1,
        "pdf": 7.0,
        "tar": 5.0,
        "office": 7.5,
    }

    encryption_map = {
        "zip": "ZIP AES-256 / PKZIP",
        "rar": "RAR AES-256",
        "7z": "7-Zip AES-256",
        "pdf": "PDF AES-128/256",
        "tar": "None (or external GPG)",
        "office": "MS Office 2007+ AES-128/256 (ECMA-376)",
    }

    strength = strength_map.get(fmt, 6.0)
    encryption = encryption_map.get(fmt, "Unknown")

    recommended = "ai_hybrid"
    if strength > 8.5 or fmt in ("7z", "rar"):
        recommended = "hashcat"
    elif strength > 7.0:
        recommended = "ai_mask_dictionary"

    return {
        "format": fmt.upper(),
        "encryption": encryption,
        "estimated_strength": round(strength, 2),
        "file_size_mb": round(size_mb, 2),
        "recommended_strategy": recommended,
        "supports_ai": True,
        "supports_resume": True,
        "hashcat_available": is_hashcat_available(),
    }


def recover(
    archive_path: str,
    hint: str,
    model: str = "llama3",
    max_candidates: int = 75,
    forced_format: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
    plugins: list[str] | None = None,
) -> str | None:
    """Orchestrate full password recovery pipeline.

    1. Load/merge session (if resuming)
    2. Generate AI candidates via Oracle (augmented by extract_context())
    3. Augment with pluggable strategies (dictionary, mask, hashcat GPU, user plugins)
    4. Rank by likelihood
    5. Test candidates in order using format-specific handlers
    6. Provide live brutalist progress UI
    7. Persist session state for resumability

    Returns the discovered password or None if exhausted.
    """
    if not Path(archive_path).is_file():
        raise FileNotFoundError(f"Cannot find archive: {archive_path}")
    if not hint or not hint.strip():
        console.print("[dim]No hint supplied – relying solely on auto-extracted context[/]")

    config = load_config()
    config.model = model
    config.max_candidates = max_candidates
    if plugins:
        config.plugin_paths = list(dict.fromkeys(config.plugin_paths + plugins))

    session = _load_or_create_session(archive_path, hint, max_candidates, resume)
    if session.found:
        console.print(brutalist_panel("Already solved in session!", session.found, style="#00ff9f"))
        return session.found

    # Generate fresh candidates if we haven't tested enough
    if len(session.tested) < config.max_candidates:
        console.print("   [bold #00ff9f]→ Calling Context Oracle (auto-context enabled)[/]")
        try:
            ai_candidates = generate_candidates(
                hint=hint,
                count=config.max_candidates * 2,
                model=config.model,
                archive_path=archive_path,
            )
        except Exception as exc:
            console.print(f"[#ff0044]Oracle failed: {exc}[/#ff0044]")
            ai_candidates = []

        # Run hybrid strategies (dictionary + mask + hashcat GPU + plugins)
        try:
            augmented = run_strategy(
                strategy="hybrid",
                candidates=ai_candidates,
                archive_path=archive_path,
                config=config,
                hint=hint,
            )
        except Exception:  # strategy registry may be incomplete
            augmented = ai_candidates

        # Merge with already-tested set while preserving order
        candidates_to_test: list[Candidate] = []
        seen = set(session.tested)
        for c in augmented:
            if c.value not in seen:
                candidates_to_test.append(c)
                seen.add(c.value)

        session.candidates = candidates_to_test[: config.max_candidates]
    else:
        candidates_to_test = session.candidates or []

    if not candidates_to_test:
        console.print("[#ff0044]No candidates generated.[/#ff0044]")
        _save_session(session)
        return None

    if dry_run:
        top = candidates_to_test[0]
        console.print(brutalist_panel("DRY-RUN — TOP CANDIDATE", top.value, style="#00ff9f"))
        _save_session(session)
        return top.value

    # Live testing with neo-brutalist progress
    found: str | None = None
    start_time = time.time()

    with Progress(
        TextColumn("[bold #ff0044]TESTING[/] {task.description}"),
        BarColumn(bar_width=None, style="#00ff9f", complete_style="#ff0044"),
        TextColumn("[bold #00ff9f]{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
        refresh_per_second=8,
    ) as progress:
        task_id = progress.add_task(
            f"[white]{Path(archive_path).name}[/]",
            total=len(candidates_to_test),
            completed=session.candidates_tested,
        )

        for idx, candidate in enumerate(candidates_to_test):
            if candidate.value in session.tested:
                progress.update(task_id, advance=1)
                continue

            session.tested.add(candidate.value)
            session.candidates_tested += 1

            progress.update(
                task_id,
                description=f"[dim]trying[/] [bold white]{candidate.value[:24]}{'…' if len(candidate.value) > 24 else ''}[/]",
                advance=1,
            )

            try:
                if try_password(archive_path, candidate.value):
                    found = sanitize_password(candidate.value)
                    session.found = found
                    progress.update(task_id, completed=len(candidates_to_test))
                    console.print(brutalist_panel("PASSWORD RECOVERED", found, style="#00ff9f"))
                    break
            except Exception as exc:  # pragma: no cover
                console.print(f"[dim]Tester error on {candidate.value}: {exc}[/]")
                continue

            # Update ETA stats every 5 tests
            if idx % 5 == 0:
                elapsed = time.time() - start_time
                if elapsed > 0 and session.candidates_tested > 3:
                    rate = session.candidates_tested / elapsed
                    remaining = (len(candidates_to_test) - session.candidates_tested) / rate
                    progress.update(task_id, description=f"[dim]rate: {rate:.1f}/s • eta: {remaining:.0f}s[/]")

    session.end_time = time.time()
    _save_session(session)

    return found


def create_job(archive_path: str, hint: str, config: Config | None = None) -> Job:
    """Create a new recovery job and persist it."""
    if config is None:
        config = load_config()
    job = Job(
        archive_path=archive_path,
        hint=hint,
        config=config,
        status="pending",
        progress=0.0,
    )
    save_job(job)
    return job


def get_job(job_id: str) -> Job | None:
    """Retrieve a job by ID (memory or disk)."""
    jobs_dir = Path(".hintforge")
    job_file = jobs_dir / f"job-{job_id}.json"
    if job_file.exists():
        try:
            with open(job_file, encoding="utf-8") as f:
                data = json.load(f)
            job = Job.model_validate(data)
            return job
        except Exception:
            pass
    return None


def update_job(job: Job) -> None:
    """Update job metadata and persist."""
    job.updated_at = datetime.now().isoformat()
    save_job(job)


def run_job(job_id: str) -> None:
    """Execute a job in background thread (called by dashboard)."""
    job = get_job(job_id)
    if not job or job.status != "pending":
        return

    job.status = "running"
    job.progress = 0.1
    update_job(job)

    try:
        password = recover(
            archive_path=job.archive_path,
            hint=job.hint,
            model=job.config.model,
            max_candidates=job.config.max_candidates,
            dry_run=False,
            resume=True,
        )
        if password:
            job.status = "done"
            job.result = password
            job.progress = 1.0
        else:
            job.status = "failed"
            job.error = "No password found in candidate space"
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)

    update_job(job)


def start_job_in_background(job_id: str) -> None:
    """Launch job execution on a background thread."""
    Thread(target=run_job, args=(job_id,), daemon=True).start()


def export_session(archive_path: str, output_path: str | None = None) -> str:
    """Export the current recovery session to a portable JSON file for sharing.

    The file contains tested candidates, found password (if any), hint and
    metadata. It can be sent to collaborators or used on another machine.
    """
    session_file = Path(".hintforge") / f"{Path(archive_path).name}.session.json"
    if not session_file.exists():
        raise FileNotFoundError(
            f"No session found for {archive_path}. "
            "Run 'hintforge recover' first to create a session."
        )

    if output_path is None:
        output_path = f"{Path(archive_path).stem}.session.json"

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(session_file, encoding="utf-8") as f:
        data = json.load(f)

    state = SessionState.model_validate(data)
    export_data = state.model_dump(mode="json")
    export_data["exported_at"] = datetime.now().isoformat()
    export_data["exported_from"] = str(Path(archive_path).absolute())

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    console.print(
        brutalist_panel(
            "SESSION EXPORTED",
            f"Saved to: {out_path}\n"
            "Share this file to let others resume your recovery work.",
            style="#00ff9f",
        )
    )
    return str(out_path)


def import_session(session_file: str, target_archive_path: str | None = None) -> SessionState:
    """Import a previously exported session file.

    If target_archive_path is supplied it overrides the embedded archive path
    (useful when the file has moved). The session is saved into .hintforge/
    so that 'recover --resume' works immediately.
    """
    path = Path(session_file)
    if not path.is_file():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        state = SessionState.model_validate(data)

        if target_archive_path:
            state.archive_path = target_archive_path

        session_dir = Path(".hintforge")
        session_dir.mkdir(parents=True, exist_ok=True)
        save_session(state)

        console.print(
            brutalist_panel(
                "SESSION IMPORTED",
                f"Archive: {Path(state.archive_path).name}\n"
                f"Tested candidates: {state.candidates_tested}\n"
                f"Password found: {state.found or 'None yet'}",
                style="#00ff9f",
            )
        )
        return state
    except Exception as exc:
        raise ValueError(f"Failed to import session: {exc}") from exc


__all__ = [
    "recover",
    "analyze",
    "create_job",
    "get_job",
    "update_job",
    "start_job_in_background",
    "export_session",
    "import_session",
    "estimate_strength",
]
