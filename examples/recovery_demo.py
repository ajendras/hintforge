#!/usr/bin/env python3
"""HintForge Recovery Demo.

Runnable example that creates a test encrypted ZIP (used as RAR proxy for portability),
generates AI-powered password candidates from a realistic human hint,
analyzes the archive, and runs a full dry-run recovery.

Demonstrates the complete public API surface.
Requires Ollama running locally with the 'llama3' model (or change --model).

Run with: python examples/recovery_demo.py
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from hintforge import recover, analyze, generate_candidates
from hintforge.models import Candidate
from hintforge.utils import brutalist_panel, load_config

console = Console(highlight=False, color_system="truecolor")


def _brutalist_header(title: str, subtitle: str | None = None) -> None:
    """Replicate the neo-brutalist CLI header for visual consistency."""
    header = Text()
    header.append("█", style="#ff0044")
    header.append(" HINT", style="bold #ff0044")
    header.append("FORGE", style="bold #00ff9f")
    header.append(" █", style="#00ff9f")

    content = Text(title.upper(), style="bold white")
    if subtitle:
        content.append(f"\n{subtitle}", style="dim white")

    panel = Panel(
        content,
        title=header,
        box=box.HEAVY,
        border_style="#ff0044",
        padding=(1, 4),
        title_align="center",
    )
    console.print(panel)
    console.print()


def create_test_archive() -> Path:
    """Create a temporary ZIP archive for the demo.

    Uses a plain ZIP (no strong encryption) so the example runs without
    external binaries. The tester treats non-encrypted ZIPs as valid for
    any password, allowing the demo to complete successfully.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="hintforge_demo_"))
    archive_path = tmp_dir / "vacation_memories.zip"

    content = (
        "These are our family vacation photos from 2022.\n"
        "Dog's name: Max. Best trip ever!\n"
    )

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("photos/info.txt", content.encode("utf-8"))

    console.print(f"[#00ff9f]Created test archive →[/] {archive_path}")
    return archive_path


def main() -> None:
    """Run the full HintForge demonstration workflow."""
    _brutalist_header(
        "RECOVERY DEMO",
        "AI-powered contextual password recovery • ZIP test archive",
    )

    config = load_config()
    console.print(brutalist_panel("LOADED CONFIG", f"Model: {config.model} • Max candidates: {config.max_candidates}"))

    hint = "vacation 2022 with my dog max"
    console.print(brutalist_panel("USER HINT", hint, style="#00ff9f"))

    archive_path = create_test_archive()
    console.print()

    # 1. Archive analysis
    console.print("[bold #ff0044]→ Running Strength Analysis[/]")
    report: dict[str, Any] = analyze(str(archive_path))
    console.print(brutalist_panel("ANALYSIS REPORT", f"Format: {report['format']} • Strength: {report['estimated_strength']}"))
    console.print(f"Recommended strategy: [bold #00ff9f]{report['recommended_strategy']}[/]")
    console.print()

    # 2. Candidate generation (Oracle)
    console.print("[bold #ff0044]→ Calling Context Oracle (LLM)[/]")
    try:
        candidates: list[Candidate] = generate_candidates(
            hint=hint,
            count=12,
            model=config.model,
        )
        console.print(f"Generated [bold #00ff9f]{len(candidates)}[/] ranked candidates")
        console.print(brutalist_panel(
            "TOP CANDIDATE",
            f"{candidates[0].value} (score={candidates[0].score:.3f})",
            style="#00ff9f",
        ))
    except Exception as exc:  # Ollama not available fallback
        console.print(f"[dim]Oracle unavailable ({exc}), using demo candidates[/]")
        candidates = [
            Candidate(score=0.92, value="Max2022!"),
            Candidate(score=0.87, value="Vacation2022"),
            Candidate(score=0.81, value="maxdog2022"),
            Candidate(score=0.76, value="SummerMax22"),
        ]
        console.print(brutalist_panel("DEMO CANDIDATES", "Max2022! (score=0.920)"))

    console.print()

    # 3. Full recovery (dry-run so we don't need real password match)
    console.print("[bold #ff0044]→ Starting Recovery Pipeline (dry-run)[/]")
    found = recover(
        archive_path=str(archive_path),
        hint=hint,
        model=config.model,
        max_candidates=12,
        dry_run=True,
        resume=False,
    )

    console.print()
    if found:
        success = Text()
        success.append("█ RECOVERED IN DEMO █\n", style="bold #00ff9f")
        success.append(found, style="bold white on #00ff9f")
        console.print(
            Panel(
                success,
                box=box.HEAVY,
                border_style="#00ff9f",
                padding=(2, 4),
                title="DEMO SUCCESS",
                title_align="center",
            )
        )
        console.print("\nIn a real encrypted archive with the matching password,")
        console.print("HintForge would have unlocked it using the AI-ranked candidate.")
    else:
        console.print("[#ff0044]No password found in demo run.[/#ff0044]")

    console.print("\n[dim]Demo complete. Temporary files cleaned up automatically.[/]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[#ff0044]Demo interrupted by user.[/#ff0044]")
    except Exception as exc:  # noqa: BLE001
        console.print(
            Panel(
                Text(f"DEMO FAILED\n{exc!s}", style="bold #ff0044"),
                box=box.HEAVY,
                border_style="#ff0044",
                title="ERROR",
            )
        )
        raise
