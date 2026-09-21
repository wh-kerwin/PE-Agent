from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from pe_agent.testing import load_scenario

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "scenarios"
EXPECTED_NAMES = {
    "pressure-drift-success",
    "recipe-change",
    "conflicting-sources",
    "fdc-timeout",
    "insufficient-evidence",
    "version-conflict",
    "permission-denied",
    "history-mismatch",
}


def test_all_eight_synthetic_scenarios_validate() -> None:
    fixtures = sorted(FIXTURE_DIR.glob("*.json"))
    scenarios = [load_scenario(path) for path in fixtures]

    assert len(scenarios) == 8
    assert {scenario.name for scenario in scenarios} == EXPECTED_NAMES
    assert all(scenario.synthetic and scenario.case.synthetic for scenario in scenarios)
    assert all(scenario.permission_profile.name for scenario in scenarios)


def test_scenario_fixtures_have_aware_timestamps() -> None:
    for path in FIXTURE_DIR.glob("*.json"):
        created_at = load_scenario(path).case.created_at
        assert created_at.tzinfo is not None
        assert created_at.utcoffset() is not None


def test_fixture_rejects_unlabeled_synthetic_data(tmp_path: Path) -> None:
    source = (FIXTURE_DIR / "pressure-drift-success.json").read_text(encoding="utf-8")
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        source.replace('"synthetic": true', '"synthetic": false', 1),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_scenario(invalid)


def test_test_clock_constant_is_aware() -> None:
    assert datetime(2026, 9, 20, tzinfo=UTC).utcoffset() is not None
