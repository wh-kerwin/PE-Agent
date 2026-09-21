import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pe_agent.domain import (
    Case,
    CaseStatus,
    CaseType,
    EntityReference,
    EntityType,
    Evidence,
    EvidenceKind,
    EvidenceQuality,
    EvidenceSource,
    Severity,
    YieldSymptom,
)

NOW = datetime(2026, 9, 20, tzinfo=UTC)


def _case_data() -> dict[str, object]:
    return {
        "caseId": "SYN-CASE",
        "caseVersion": "1",
        "caseType": "YIELD_DROP",
        "severity": "HIGH",
        "status": "OPEN",
        "processStep": "SYNTHETIC_ETCH",
        "createdAt": "2026-09-20T00:00:00Z",
        "lotIds": ["SYN-LOT"],
        "toolIds": [],
        "recipeIds": [],
        "symptom": {"observedYieldPercent": 82.0, "baselineYieldPercent": 96.0},
        "synthetic": True,
    }


def test_case_is_strict_and_calculates_percentage_points() -> None:
    case = Case.model_validate_json(json.dumps(_case_data()))

    assert case.case_type is CaseType.YIELD_DROP
    assert case.status is CaseStatus.OPEN
    assert case.severity is Severity.HIGH
    assert case.symptom.absolute_drop_percentage_points == 14.0


def test_case_requires_a_lot() -> None:
    data = _case_data()
    data["lotIds"] = []

    with pytest.raises(ValidationError, match="at least 1 item"):
        Case.model_validate_json(json.dumps(data))


def test_domain_models_forbid_unknown_fields_and_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Case.model_validate_json(json.dumps({**_case_data(), "tenantId": "untrusted"}))

    data = _case_data()
    data["createdAt"] = datetime(2026, 9, 20)
    with pytest.raises(ValidationError, match="UTC offset"):
        Case.model_validate(data)


def test_yield_drop_rejects_non_drop_values() -> None:
    with pytest.raises(ValidationError, match="observed yield below baseline"):
        YieldSymptom(observed_yield_percent=96.0, baseline_yield_percent=96.0)


def test_source_gap_cannot_be_modeled_as_evidence() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="EV-GAP",
            kind=EvidenceKind.FDC,
            observation=None,
            source=EvidenceSource(system="SYNTHETIC_FDC", source_id="SYN-FDC"),
            entity_refs=(EntityReference(type=EntityType.TOOL, id="SYN-TOOL"),),
            event_time=None,
            retrieved_at=NOW,
            quality="UNAVAILABLE",
            raw_ref=None,
            warnings=("Synthetic source timed out",),
        )


def test_evidence_requires_event_time() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="EV-BAD",
            kind=EvidenceKind.SPC,
            observation="Synthetic observation",
            source=EvidenceSource(system="SYNTHETIC_SPC", source_id="SYN-SPC"),
            entity_refs=(EntityReference(type=EntityType.TOOL, id="SYN-TOOL"),),
            event_time=None,
            retrieved_at=NOW,
            quality=EvidenceQuality.VERIFIED,
            raw_ref="/api/ai/source-links/EV-BAD",
        )
