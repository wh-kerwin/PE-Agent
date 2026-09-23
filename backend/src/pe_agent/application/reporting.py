from __future__ import annotations

import json
import re
from datetime import datetime
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from pe_agent.domain import (
    DecisionPrimitive,
    DecisionResult,
    Evidence,
    EvidenceKind,
    EvidenceQuality,
    HistoricalCaseEvidence,
    ReportInput,
    ReportOutcome,
    TaskStatus,
    ToolStatus,
    YieldEvidence,
)

_CAUSAL_CLAIM = re.compile(
    r"\bconfirmed root cause\b|\broot cause\s+(?:is|was|were)\b|"
    r"\b(?:is|was|were)\s+caused by\b|\b(?:due to|because|therefore)\b|"
    r"根因|由于|因此|导致",
    re.IGNORECASE,
)


def compose_report(report_input: ReportInput) -> ReportOutcome:
    evidence = tuple(
        sorted(
            (item for result in report_input.results for item in result.evidence),
            key=lambda item: (item.event_time, item.evidence_id),
        )
    )
    current_evidence = tuple(
        item for item in evidence if item.kind is not EvidenceKind.HISTORICAL_CASE
    )
    preflight_errors = _preflight_errors(report_input, evidence, current_evidence)
    if preflight_errors:
        return ReportOutcome(None, TaskStatus.FAILED, preflight_errors)

    case = report_input.context.case
    uncertainties = _uncertainties(report_input)
    if report_input.decision is None:
        uncertainties.append(
            {
                "uncertaintyId": f"U-{len(uncertainties) + 1:02d}",
                "description": "Model assessment was unavailable.",
                "impact": (
                    "No model-scored hypothesis is included; an engineer must review the "
                    "source observations directly."
                ),
                "relatedEvidenceIds": [item.evidence_id for item in current_evidence],
            }
        )
    report: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "reportId": f"RPT-{report_input.task_id}-V{report_input.report_version}",
        "taskId": report_input.task_id,
        "reportVersion": report_input.report_version,
        "caseSnapshot": {
            "caseId": case.case_id,
            "caseVersion": case.case_version,
            "caseType": case.case_type.value,
        },
        "generatedAt": report_input.generated_at.isoformat(),
        "model": {
            "provider": "typesafe",
            "requestedModel": report_input.requested_model,
            "resolvedModel": report_input.resolved_model,
            "questionSetVersion": report_input.question_set_version,
        },
        "summary": {
            "title": f"Yield drop analysis for {case.case_id}",
            "overview": _overview(current_evidence, uncertainties),
            "severity": case.severity.value,
        },
        "impact": {
            "yield": {
                "observedPercent": case.symptom.observed_yield_percent,
                "baselinePercent": case.symptom.baseline_yield_percent,
                "absoluteDropPercentagePoints": (
                    case.symptom.absolute_drop_percentage_points
                ),
            },
            "affectedLots": list(case.lot_ids),
            "affectedWafers": [],
            "affectedTools": list(case.tool_ids),
        },
        "timeline": [
            {
                "eventId": f"TL-{index:02d}",
                "occurredAt": item.event_time.isoformat(),
                "title": _timeline_title(item),
                "evidenceIds": [item.evidence_id],
            }
            for index, item in enumerate(current_evidence, 1)
        ],
        "findings": [
            {
                "findingId": f"F-{index:02d}",
                "level": "OBSERVED",
                "title": _finding_title(item),
                "description": item.observation,
                "evidenceIds": [item.evidence_id],
            }
            for index, item in enumerate(current_evidence, 1)
        ],
        "evidence": [_serialize_evidence(item) for item in evidence],
        "correlations": _correlations(current_evidence),
        "hypotheses": _hypotheses(report_input, current_evidence),
        "similarCases": _similar_cases(report_input, evidence),
        "recommendations": _recommendations(current_evidence),
        "uncertainties": uncertainties,
    }
    errors = validate_report(
        report,
        source_evidence=evidence,
        allowed_entity_ids=report_input.authorized_entity_ids,
        expected_identity=(
            report_input.task_id,
            report_input.report_version,
            case.case_id,
            case.case_version,
        ),
        expected_model=(
            report_input.requested_model,
            report_input.resolved_model,
            report_input.question_set_version,
        ),
        expected_yield=(
            case.symptom.observed_yield_percent,
            case.symptom.baseline_yield_percent,
            case.symptom.absolute_drop_percentage_points,
        ),
        decision=report_input.decision,
    )
    if errors:
        return ReportOutcome(None, TaskStatus.FAILED, errors)
    partial = bool(uncertainties) or any(
        item.quality is not EvidenceQuality.VERIFIED for item in current_evidence
    )
    status = TaskStatus.PARTIAL_RESULT if partial else TaskStatus.COMPLETED
    return ReportOutcome(report, status)


def attach_expression(
    outcome: ReportOutcome,
    *,
    expression: dict[str, Any],
) -> ReportOutcome:
    if outcome.report is None:
        return outcome
    text = expression.get("text")
    if not isinstance(text, str) or _CAUSAL_CLAIM.search(text):
        return outcome
    report = dict(outcome.report)
    report["expression"] = expression
    errors = [
        f"schema {list(error.absolute_path)}: {error.message}"
        for error in _validator().iter_errors(report)
    ]
    if errors:
        return outcome
    return ReportOutcome(report, outcome.terminal_status, outcome.validation_errors)


def validate_report(
    report: dict[str, Any],
    *,
    source_evidence: tuple[Evidence, ...],
    allowed_entity_ids: frozenset[str],
    expected_identity: tuple[str, int, str, str] | None = None,
    expected_model: tuple[str, str, str],
    expected_yield: tuple[float, float, float],
    decision: DecisionResult | None = None,
) -> tuple[str, ...]:
    errors = [
        f"schema {list(error.absolute_path)}: {error.message}"
        for error in _validator().iter_errors(report)
    ]
    if errors:
        return tuple(errors)
    if expected_identity is not None:
        expected_task_id, expected_report_version, expected_case_id, expected_case_version = (
            expected_identity
        )
        case_snapshot = report.get("caseSnapshot")
        if (
            report.get("taskId") != expected_task_id
            or report.get("reportVersion") != expected_report_version
            or not isinstance(case_snapshot, dict)
            or case_snapshot.get("caseId") != expected_case_id
            or case_snapshot.get("caseVersion") != expected_case_version
        ):
            errors.append("report identity metadata does not match canonical input")
    evidence_items = report.get("evidence", [])
    if not isinstance(evidence_items, list):
        return tuple(errors)

    evidence_ids = [
        item.get("evidenceId") for item in evidence_items if isinstance(item, dict)
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("evidence IDs must be unique")
    valid_ids: set[str] = {
        item for item in evidence_ids if isinstance(item, str)
    }
    source_ids = {item.evidence_id for item in source_evidence}
    if valid_ids != source_ids:
        errors.append("report evidence IDs must exactly match canonical source evidence")
    missing = sorted(_references(report) - valid_ids)
    if missing:
        errors.append(f"unknown evidence references: {missing}")

    timeline = report.get("timeline", [])
    occurred = [
        parsed
        for item in timeline
        if isinstance(item, dict)
        and (parsed := _parse_timestamp(item.get("occurredAt"))) is not None
    ]
    if occurred != sorted(occurred):
        errors.append("timeline must be chronological")

    serialized = {
        item["evidenceId"]: item
        for item in evidence_items
        if isinstance(item, dict) and isinstance(item.get("evidenceId"), str)
    }
    for source in source_evidence:
        if serialized.get(source.evidence_id) != _serialize_evidence(source):
            errors.append(
                f"evidence {source.evidence_id} does not preserve its canonical source"
            )
        if source.retrieved_at < source.event_time:
            errors.append(
                f"evidence {source.evidence_id} was retrieved before its event time"
            )
        for entity in source.entity_refs:
            if (
                entity.type.value
                in {"CASE", "LOT", "WAFER", "TOOL", "CHAMBER", "RECIPE"}
                and entity.id not in allowed_entity_ids
            ):
                errors.append(
                    f"evidence {source.evidence_id} references an unauthorized entity"
                )

    generated_at = _parse_timestamp(report.get("generatedAt"))
    if generated_at is None:
        errors.append("generatedAt must be an offset-aware timestamp")
    elif any(generated_at < item.retrieved_at for item in source_evidence):
        errors.append("report was generated before evidence retrieval")

    _validate_yield_math(report, expected_yield, errors)
    _validate_model(report, expected_model, decision, errors)
    _validate_historical_support(report, source_evidence, errors)
    if any(_CAUSAL_CLAIM.search(text) for text in _generated_report_text(report)):
        errors.append("report contains an unverified causal claim")
    return tuple(dict.fromkeys(errors))


def _preflight_errors(
    report_input: ReportInput,
    evidence: tuple[Evidence, ...],
    current_evidence: tuple[Evidence, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    if not current_evidence:
        errors.append("INSUFFICIENT_EVIDENCE")
    ids = [item.evidence_id for item in evidence]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_EVIDENCE_ID")
    if report_input.report_version < 1:
        errors.append("INVALID_REPORT_VERSION")
    if (
        report_input.generated_at.tzinfo is None
        or report_input.generated_at.utcoffset() is None
    ):
        errors.append("INVALID_GENERATED_AT")
    case_yield = report_input.context.case.symptom
    for result in report_input.results:
        if (
            result.tool_id == "get_lot_yield"
            and isinstance(result.data, YieldEvidence)
            and (
                result.data.observed_percent != case_yield.observed_yield_percent
                or result.data.baseline_percent != case_yield.baseline_yield_percent
            )
        ):
            errors.append("YIELD_EVIDENCE_CONFLICT")
    if report_input.decision is not None and (
        report_input.decision.requested_model != report_input.requested_model
        or report_input.decision.resolved_model != report_input.resolved_model
        or report_input.decision.question_set_version
        != report_input.question_set_version
    ):
        errors.append("DECISION_METADATA_MISMATCH")
    return tuple(dict.fromkeys(errors))


def _validator() -> Draft202012Validator:
    schema = json.loads(
        files("pe_agent")
        .joinpath("analysis-report.schema.json")
        .read_text(encoding="utf-8")
    )
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _serialize_evidence(item: Evidence) -> dict[str, Any]:
    return {
        "evidenceId": item.evidence_id,
        "kind": item.kind.value,
        "observation": item.observation,
        "source": {"system": item.source.system, "sourceId": item.source.source_id},
        "entityRefs": [
            {"type": entity.type.value, "id": entity.id} for entity in item.entity_refs
        ],
        "eventTime": item.event_time.isoformat(),
        "retrievedAt": item.retrieved_at.isoformat(),
        "quality": item.quality.value,
        "rawRef": item.raw_ref,
    }


def _uncertainties(report_input: ReportInput) -> list[dict[str, Any]]:
    candidates: list[tuple[str, tuple[str, ...]]] = []
    for result in report_input.results:
        evidence_ids = tuple(item.evidence_id for item in result.evidence)
        if result.status is ToolStatus.FAILED:
            candidates.append((f"{result.tool_id} was unavailable", evidence_ids))
        elif result.status is ToolStatus.PARTIAL:
            candidates.append((f"{result.tool_id} returned partial data", evidence_ids))
        candidates.extend((warning, evidence_ids) for warning in result.quality.warnings)
        for item in result.evidence:
            candidates.extend(
                (warning, (item.evidence_id,)) for warning in item.warnings
            )
            if item.quality is EvidenceQuality.PARTIAL:
                candidates.append(
                    (f"{result.tool_id} contains partial evidence", (item.evidence_id,))
                )
            elif item.quality is EvidenceQuality.CONFLICTING:
                candidates.append(
                    (f"{result.tool_id} conflicts with another source", evidence_ids)
                )
    unique = list(dict.fromkeys(candidates))
    return [
        {
            "uncertaintyId": f"U-{index:02d}",
            "description": description,
            "impact": (
                "An engineer must verify this gap before relying on the related "
                "interpretation."
            ),
            "relatedEvidenceIds": list(evidence_ids),
        }
        for index, (description, evidence_ids) in enumerate(unique, 1)
    ]


def _correlations(evidence: tuple[Evidence, ...]) -> list[dict[str, Any]]:
    process = [
        item for item in evidence if item.kind in {EvidenceKind.SPC, EvidenceKind.FDC}
    ]
    if len(process) < 2:
        return []
    return [
        {
            "correlationId": "C-01",
            "type": "TEMPORAL",
            "description": (
                "The cited process observations occurred within the analyzed case window."
            ),
            "evidenceIds": [item.evidence_id for item in process],
        }
    ]


def _hypotheses(
    report_input: ReportInput,
    evidence: tuple[Evidence, ...],
) -> list[dict[str, Any]]:
    decision = report_input.decision
    pressure = [
        item
        for item in evidence
        if item.kind in {EvidenceKind.SPC, EvidenceKind.FDC}
        and "pressure" in item.observation.lower()
    ]
    supporting = [
        item for item in pressure if item.quality is not EvidenceQuality.CONFLICTING
    ]
    contradicting = [
        item for item in pressure if item.quality is EvidenceQuality.CONFLICTING
    ]
    if not supporting or decision is None:
        return []
    assessment = next(
        (item for item in decision.answers if item.question_id == "pressure_drift_support"),
        None,
    )
    if (
        assessment is None
        or assessment.primitive is not DecisionPrimitive.SCORE
        or not isinstance(assessment.answer, float)
    ):
        return []
    score = assessment.answer
    confidence_level = "HIGH" if score >= 2.5 else "MEDIUM" if score >= 1.5 else "LOW"
    return [
        {
            "hypothesisId": "H-01",
            "title": "Chamber-pressure observations may be associated with the yield loss",
            "confidenceLevel": confidence_level,
            "supportingEvidenceIds": [item.evidence_id for item in supporting],
            "contradictingEvidenceIds": [
                item.evidence_id for item in contradicting
            ],
            "missingEvidence": ["Engineer verification of the suspected pressure path"],
            "modelAssessment": {
                "questionId": assessment.question_id,
                "primitive": assessment.primitive.value,
                "answer": assessment.answer,
                "distribution": assessment.distribution,
                "confidence": assessment.confidence,
                "resolvedModel": decision.resolved_model,
            },
        }
    ]


def _similar_cases(
    report_input: ReportInput,
    evidence: tuple[Evidence, ...],
) -> list[dict[str, str]]:
    historical = {
        item.source.source_id: item
        for item in evidence
        if item.kind is EvidenceKind.HISTORICAL_CASE
    }
    values: list[dict[str, str]] = []
    for result in report_input.results:
        if isinstance(result.data, HistoricalCaseEvidence):
            for case_id in result.data.case_ids:
                item = historical.get(case_id)
                if item is not None:
                    values.append(
                        {
                            "caseId": case_id,
                            "similarityReason": (
                                "The adapter returned this resolved case as a match; it is "
                                "context only."
                            ),
                            "evidenceId": item.evidence_id,
                        }
                    )
    return values


def _recommendations(evidence: tuple[Evidence, ...]) -> list[dict[str, Any]]:
    grouped: dict[EvidenceKind, list[str]] = {}
    for item in evidence:
        grouped.setdefault(item.kind, []).append(item.evidence_id)
    templates = {
        EvidenceKind.SPC: "Review the cited SPC rule and its active control limits.",
        EvidenceKind.FDC: "Verify the cited sensor trend and calibration status.",
        EvidenceKind.RECIPE: "Compare the cited recipe snapshot with the approved version.",
        EvidenceKind.YIELD: "Compare the next authorized run with the same yield baseline.",
        EvidenceKind.TOOL_EVENT: "Review the cited tool events with equipment engineering.",
    }
    values: list[dict[str, Any]] = []
    for kind, action in templates.items():
        evidence_ids = grouped.get(kind)
        if evidence_ids:
            values.append(
                {
                    "recommendationId": f"REC-{len(values) + 1:02d}",
                    "category": (
                        "FOLLOW_UP" if kind is EvidenceKind.YIELD else "INVESTIGATION"
                    ),
                    "action": action,
                    "reason": "This action checks an observation from the current case.",
                    "evidenceIds": evidence_ids,
                    "requiresEngineerDecision": True,
                }
            )
    return values


def _overview(
    evidence: tuple[Evidence, ...], uncertainties: list[dict[str, Any]]
) -> str:
    base = f"The report contains {len(evidence)} current, source-linked observations."
    if uncertainties:
        return f"{base} Material gaps or conflicts remain for engineering review."
    return f"{base} Interpretations remain subject to engineering verification."


def _timeline_title(item: Evidence) -> str:
    return f"{item.kind.value.replace('_', ' ').title()} observation recorded"


def _finding_title(item: Evidence) -> str:
    return f"Observed {item.kind.value.replace('_', ' ').lower()} evidence"


def _references(report: dict[str, Any]) -> set[str]:
    references: set[str] = set()
    for section in ("timeline", "findings", "correlations", "recommendations"):
        for item in report.get(section, []):
            references.update(item.get("evidenceIds", []))
    for item in report.get("hypotheses", []):
        references.update(item.get("supportingEvidenceIds", []))
        references.update(item.get("contradictingEvidenceIds", []))
    for item in report.get("similarCases", []):
        evidence_id = item.get("evidenceId")
        if isinstance(evidence_id, str):
            references.add(evidence_id)
    for item in report.get("uncertainties", []):
        references.update(item.get("relatedEvidenceIds", []))
    return references


def _validate_yield_math(
    report: dict[str, Any],
    expected: tuple[float, float, float],
    errors: list[str],
) -> None:
    impact = report.get("impact", {})
    values = impact.get("yield", {}) if isinstance(impact, dict) else {}
    if not isinstance(values, dict):
        return
    observed = _number(values.get("observedPercent"))
    baseline = _number(values.get("baselinePercent"))
    drop = _number(values.get("absoluteDropPercentagePoints"))
    if (
        observed is not None
        and baseline is not None
        and drop is not None
        and (
            abs(baseline - observed - drop) > 1e-6
            or any(
                abs(actual - canonical) > 1e-6
                for actual, canonical in zip(
                    (observed, baseline, drop), expected, strict=True
                )
            )
        )
    ):
        errors.append("yield impact does not match canonical inputs")


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _validate_model(
    report: dict[str, Any],
    expected: tuple[str, str, str],
    decision: DecisionResult | None,
    errors: list[str],
) -> None:
    model = report.get("model")
    if not isinstance(model, dict):
        return
    actual = (
        model.get("requestedModel"),
        model.get("resolvedModel"),
        model.get("questionSetVersion"),
    )
    if actual != expected:
        errors.append("report model metadata does not match the analysis input")
    assessments = {
        item.get("modelAssessment", {}).get("questionId"): item.get(
            "modelAssessment", {}
        )
        for item in report.get("hypotheses", [])
        if isinstance(item, dict)
        and isinstance(item.get("modelAssessment"), dict)
    }
    if not assessments:
        return
    if decision is None:
        errors.append("model assessments require a decision result")
        return
    answers = {item.question_id: item for item in decision.answers}
    if not set(assessments) <= set(answers):
        errors.append("model assessment references an unknown decision question")
        return
    for question_id, assessment in assessments.items():
        answer = answers[question_id]
        expected_assessment = {
            "questionId": answer.question_id,
            "primitive": answer.primitive.value,
            "answer": answer.answer,
            "distribution": answer.distribution,
            "confidence": answer.confidence,
            "resolvedModel": decision.resolved_model,
        }
        if assessment != expected_assessment:
            errors.append("model assessment does not preserve the decision result")


def _validate_historical_support(
    report: dict[str, Any], source_evidence: tuple[Evidence, ...], errors: list[str]
) -> None:
    historical_ids = {
        item.evidence_id
        for item in source_evidence
        if item.kind is EvidenceKind.HISTORICAL_CASE
    }
    for section in ("findings", "correlations", "recommendations"):
        for item in report.get(section, []):
            references = set(item.get("evidenceIds", []))
            if references and references <= historical_ids:
                errors.append(f"{section} cannot rely only on historical evidence")
    for item in report.get("hypotheses", []):
        references = set(item.get("supportingEvidenceIds", []))
        if references and references <= historical_ids:
            errors.append("hypotheses cannot rely only on historical evidence")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _generated_report_text(report: dict[str, Any]) -> list[str]:
    sections = (
        report.get("summary"),
        report.get("timeline"),
        report.get("findings"),
        report.get("correlations"),
        report.get("hypotheses"),
        report.get("recommendations"),
        report.get("uncertainties"),
    )
    return [text for section in sections for text in _nested_text(section)]


def _nested_text(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for nested in value.values() for text in _nested_text(nested)]
    if isinstance(value, list):
        return [text for nested in value for text in _nested_text(nested)]
    return []
