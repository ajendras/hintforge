"""Unit and integration tests for HintForge tester and session export/import."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from hintforge.core import export_session, import_session
from hintforge.handlers import PasswordError, detect_format
from hintforge.models import Candidate, SessionState
from hintforge.tester import try_password


def test_detect_format():
    """Basic format detection tests."""
    assert detect_format("test.zip") == "zip"
    assert detect_format("test.rar") == "rar"
    assert detect_format("test.pdf") == "pdf"
    assert detect_format("test.7z") == "7z"
    assert detect_format("document.docx") == "office"


@pytest.mark.parametrize("fmt,ext", [("zip", "zip"), ("rar", "rar"), ("pdf", "pdf")])
def test_try_password_raises_on_bad_password(fmt: str, ext: str, mocker: MockerFixture):
    """Wrong password must raise PasswordError."""
    mocker.patch(
        "hintforge.tester.open_with_password",
        side_effect=PasswordError("bad password"),
    )
    with pytest.raises(PasswordError):
        try_password(f"fake.{ext}", "wrongpass")


def test_session_export_import(tmp_path: Path, mocker: MockerFixture):
    """Test that sessions can be exported and imported for sharing."""
    archive = tmp_path / "protected.rar"
    archive.touch()
    session_dir = tmp_path / ".hintforge"
    session_dir.mkdir()
    session_file = session_dir / "protected.rar.session.json"

    test_candidates = [Candidate(score=0.95, value="Dog2020!")]
    state = SessionState(
        archive_path=str(archive),
        hint="my dog born 2020",
        candidates_tested=42,
        total_candidates=100,
        tested={"bad1", "bad2"},
        found=None,
        candidates=test_candidates,
    )

    # Write initial session file
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(mode="json"), f, indent=2)

    # Mock side-effects
    mocker.patch("hintforge.core.console.print")
    mocker.patch("hintforge.core.save_session")

    # Test export
    export_path = tmp_path / "shared.session.json"
    result_path = export_session(str(archive), str(export_path))
    assert Path(result_path).exists()

    exported_data = json.loads(Path(export_path).read_text(encoding="utf-8"))
    assert exported_data["hint"] == state.hint
    assert exported_data["version"] == "0.2.0"
    assert "exported_at" in exported_data
    assert "exported_from" in exported_data

    # Test import (with archive override)
    new_archive = str(tmp_path / "copy.rar")
    imported_state = import_session(str(export_path), new_archive)
    assert imported_state.archive_path == new_archive
    assert imported_state.hint == state.hint
    assert imported_state.candidates_tested == 42
    assert imported_state.version == "0.2.0"

    # Test that a found password survives round-trip
    state.found = "Dog2020!"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(mode="json"), f, indent=2)
    imported_with_found = import_session(str(export_path))
    assert imported_with_found.found == "Dog2020!"
