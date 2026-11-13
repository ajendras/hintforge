"""Command-line interface for HintForge.

Implements a loud neo-brutalist terminal UI using Rich with
thick borders (via HEAVY box), primary colours #ff0044 and #00ff9f,
chunky mono-style text and hard offset visual language.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.table import Table

from . import __version__
from .core import recover, analyze
from .oracle import generate_candidates
from .models import Candidate

console = Console(highlight=False, color_system="truecolor")


def _brutalist_header(title: str, subtitle: str | None = None) -> None:
    """Render chunky neo-brutalist header with primary palette."""
    header = Text()
    header.append("█", style="#ff0044")
    header.append(" HINT", style="bold #ff0044")
    header.append("FORGE", style="bold #00ff9f")
    header.append(" █", style="#00ff9f")

    content = Text()
    content.append(title.upper(), style="bold white")
    if subtitle:
        content.append("\n" + subtitle, style="dim white")

    panel = Panel(
        content,
        title=header,
        box=box.HEAVY,
        border_style="#ff0044",
        padding=(1, 2),
        title_align="center",
        subtitle=subtitle or "AI CONTEXTUAL CRACKER",
        subtitle_align="center",
    )
    console.print(panel)
    console.print()


def _validate_positive(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Click callback to enforce positive integers."""
    if value <= 0:
        raise click.BadParameter("must be greater than zero")
    return value


@click.group()
@click.version_option(__version__, "--version", "-V", help="Show version and exit")
def cli() -> None:
    """HintForge — LLM-powered archive password recovery.

    Turns vague human memories into intelligently ranked password
    candidates and tests them against encrypted archives.
    """
    pass


@cli.command(name="recover")
@click.argument(
    "archive",
    type=click.Path(exists=True, dir_okay=False, path_type=Path, readable=True),
)
@click.option(
    "--hint",
    "-h",
    required=True,
    help="Contextual memory about the password (e.g. 'dog name 2019 vacation')",
)
@click.option(
    "--model",
    "-m",
    default="llama3",
    help="Ollama model name",
    show_default=True,
)
@click.option(
    "--max-candidates",
    "-c",
    default=75,
    callback=_validate_positive,
    type=int,
    help="Maximum candidates to generate and test",
    show_default=True,
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["auto", "zip", "rar", "pdf", "7z", "tar"]),
    default="auto",
    help="Force archive format (default: auto-detect)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Generate candidates only, do not test against archive",
)
@click.option(
    "--resume",
    is_flag=True,
    help="Resume from previous session checkpoint if available",
)
def recover_cmd(
    archive: Path,
    hint: str,
    model: str,
    max_candidates: int,
    format: str,
    dry_run: bool,
    resume: bool,
) -> None:
    """Recover password for an encrypted archive using AI-generated candidates."""
    _brutalist_header(
        "RECOVERY MISSION ACTIVE",
        f"Target: {archive.name} • Model: {model} • Candidates: {max_candidates}",
    )

    if not hint.strip():
        console.print("[#ff0044]ERROR: Hint cannot be empty.[/#ff0044]")
        raise click.Abort()

    console.print(Text("→ Calling Context Oracle...", style="#00ff9f"))
    console.print()

    try:
        password = recover(
            archive_path=str(archive),
            hint=hint,
            model=model,
            max_candidates=max_candidates,
            forced_format=format if format != "auto" else None,
            dry_run=dry_run,
            resume=resume,
        )

        if password:
            success = Text()
            success.append("█ PASSWORD RECOVERED █\n", style="bold #00ff9f")
            success.append(password, style="bold white on #00ff9f")
            console.print(
                Panel(
                    success,
                    box=box.HEAVY,
                    border_style="#00ff9f",
                    padding=(2, 4),
                    title="SUCCESS",
                    title_align="center",
                )
            )
        else:
            fail = Text("NO MATCH FOUND IN CANDIDATE SPACE", style="bold #ff0044")
            console.print(
                Panel(
                    fail,
                    box=box.HEAVY,
                    border_style="#ff0044",
                    padding=(2, 4),
                )
            )
            if not dry_run:
                console.print(
                    "\nTry a richer hint or increase --max-candidates.",
                    style="dim white",
                )
    except Exception as exc:  # noqa: BLE001 - CLI top-level handler
        console.print(
            Panel(
                Text(f"CRITICAL FAILURE\n{exc!s}", style="bold #ff0044"),
                title="MISSION ABORTED",
                box=box.HEAVY,
                border_style="#ff0044",
            )
        )
        sys.exit(1)


@cli.command(name="analyze")
@click.argument(
    "archive",
    type=click.Path(exists=True, dir_okay=False, path_type=Path, readable=True),
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["auto", "zip", "rar", "pdf", "7z", "tar"]),
    default="auto",
    help="Force archive format (default: auto-detect)",
)
def analyze_cmd(archive: Path, format: str) -> None:
    """Analyze encryption strength and recommend attack strategy."""
    _brutalist_header("ARCHIVE STRENGTH ANALYSIS", archive.name)

    try:
        report = analyze(
            archive_path=str(archive),
            forced_format=format if format != "auto" else None,
        )

        table = Table(
            box=box.HEAVY,
            border_style="#00ff9f",
            title="ANALYSIS REPORT",
            title_style="bold #ff0044",
            padding=(0, 2),
        )
        table.add_column("PROPERTY", style="#00ff9f", no_wrap=True)
        table.add_column("VALUE", style="white")

        for key, value in report.items():
            if isinstance(value, float):
                value = f"{value:.3f}"
            table.add_row(key.upper(), str(value))

        console.print(table)
        console.print()

        if report.get("recommended_strategy"):
            console.print(
                Text(
                    f"RECOMMENDED: {report['recommended_strategy'].upper()}",
                    style="bold #00ff9f",
                )
            )
    except Exception as exc:  # noqa: BLE001
        console.print(
            Panel(
                Text(f"ANALYSIS FAILED\n{exc!s}", style="#ff0044"),
                box=box.HEAVY,
                border_style="#ff0044",
            )
        )
        sys.exit(1)


@cli.command(name="generate")
@click.option(
    "--hint",
    "-h",
    required=True,
    help="Contextual memory / hint",
)
@click.option(
    "--count",
    "-c",
    default=50,
    callback=_validate_positive,
    type=int,
    help="Number of candidates to generate",
    show_default=True,
)
@click.option(
    "--model",
    "-m",
    default="llama3",
    help="Ollama model",
    show_default=True,
)
@click.option(
    "--min-score",
    default=0.0,
    type=float,
    help="Minimum likelihood score to display",
)
def generate_cmd(hint: str, count: int, model: str, min_score: float) -> None:
    """Generate ranked password candidates from a natural-language hint."""
    _brutalist_header("CANDIDATE GENERATION", f"Model: {model} • Count: {count}")

    if not hint or not hint.strip():
        console.print("[#ff0044]Hint must not be blank.[/#ff0044]")
        raise click.Abort()

    try:
        candidates: list[Candidate] = generate_candidates(
            hint=hint.strip(),
            count=count,
            model=model,
        )

        # Filter by minimum score
        filtered = [c for c in candidates if c.score >= min_score]
        if not filtered:
            console.print("No candidates above minimum score.", style="dim")
            return

        table = Table(
            box=box.HEAVY,
            border_style="#ff0044",
            header_style="bold #00ff9f",
            title="RANKED CANDIDATES",
        )
        table.add_column("RANK", justify="right", style="#00ff9f")
        table.add_column("PASSWORD", style="bold white")
        table.add_column("SCORE", justify="right")

        for i, candidate in enumerate(filtered[:30], 1):  # limit display
            score_str = f"{candidate.score:.3f}"
            table.add_row(str(i), candidate.value, score_str)

        console.print(table)
        console.print(f"\nTotal generated: {len(candidates)}", style="dim white")

        if len(filtered) > 30:
            console.print(
                f"... and {len(filtered) - 30} more below display limit.",
                style="dim",
            )
    except Exception as exc:  # noqa: BLE001
        console.print(
            Panel(
                Text(f"GENERATION FAILED\n{exc!s}", style="bold #ff0044"),
                box=box.HEAVY,
                border_style="#ff0044",
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    cli()
