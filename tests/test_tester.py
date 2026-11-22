"""Tests for HintForge tester and the new built-in strength estimator."""

import pytest
from unittest.mock import patch, MagicMock

from hintforge.core import estimate_strength
from hintforge.models import StrengthReport, Config
from hintforge.tester import try_password
from hintforge.handlers import PasswordError, detect_format


def test_estimate_strength_weak_password():
    report = estimate_strength("123456")
    assert isinstance(report, StrengthReport)
    assert report.entropy_bits < 30.0
    assert report.strength == "very weak"
    assert any("easy" in f.lower() or "never" in f.lower() for f in report.feedback)


def test_estimate_strength_strong_password():
    pw = "Tr0ub4dor&3xpl0r3rX2023!"
    report = estimate_strength(pw)
    assert report.entropy_bits > 90.0
    assert report.strength in ("strong", "very strong")
    assert len(report.crack_times) == 3
    assert "centuries" in report.crack_times["gpu_offline"] or "years" in report.crack_times["gpu_offline"]


def test_estimate_strength_with_custom_config():
    config = Config(
        online_guesses_per_second=100,
        cpu_guesses_per_second=10000,
        gpu_guesses_per_second=50000,
    )
    report = estimate_strength("testpass123!", config=config)
    assert isinstance(report.crack_times, dict)
    assert "online" in report.crack_times
    assert report.entropy_bits > 40.0


def test_estimate_strength_empty_password():
    report = estimate_strength("")
    assert report.strength == "invalid"
    assert report.entropy_bits == 0.0
    assert len(report.feedback) > 0


def test_estimate_strength_common_pattern_penalty():
    report = estimate_strength("MyDogMax2020")
    # personal info + common pattern should reduce entropy
    assert report.entropy_bits < 55.0
    assert any("personal" in f.lower() or "pattern" in f.lower() for f in report.feedback)


# Original tester tests (mocked for CI compatibility)
@patch("hintforge.tester.open_with_password")
def test_try_password_success(mock_open_with_password):
    mock_open_with_password.return_value.__enter__.return_value = MagicMock()
    assert try_password("test.zip", "correct-password") is True


@patch("hintforge.tester.open_with_password")
def test_try_password_failure(mock_open_with_password):
    mock_open_with_password.side_effect = PasswordError("Incorrect password")
    assert try_password("test.zip", "wrong") is False


def test_detect_format():
    # Basic sanity check (real tests use temp fixtures)
    assert detect_format("example.zip") == "zip"
    assert detect_format("example.rar") == "rar"
    assert detect_format("document.docx") == "office"


@pytest.mark.parametrize("pw,expected_min_entropy", [
    ("abc", 10),
    ("P@ssw0rd2023!", 60),
])
def test_estimate_strength_parametrized(pw, expected_min_entropy):
    report = estimate_strength(pw)
    assert report.entropy_bits >= expected_min_entropy
