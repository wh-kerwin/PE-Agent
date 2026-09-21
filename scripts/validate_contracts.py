import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def load(path: str) -> dict[str, Any] | None:
    try:
        value = json.loads((ROOT / path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            errors.append(f"{path}: top-level JSON value must be an object")
            return None
        return value
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None

schema = load("agent/schemas/analysis-report.schema.json")
report = load("examples/analysis-result.json")
tools = load("agent/tools/tool-registry.json")
workflow = load("agent/workflow/yield-drop.workflow.json")
questions = load("agent/jev-questions.json")
load("agent/model-profile.json")
load("examples/case-yield-drop.json")
jev_example = load("examples/jev-assessment.json")

if schema and report:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        errors.append(f"analysis-report.schema.json: invalid schema: {exc}")
    for err in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(report):
        errors.append(f"analysis-result.json {list(err.absolute_path)}: {err.message}")
    evidence_ids = [item["evidenceId"] for item in report.get("evidence", [])]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("analysis-result.json: duplicate evidenceId")
    valid_ids = set(evidence_ids)
    references = []
    for name in ("timeline", "findings", "correlations", "recommendations"):
        for item in report.get(name, []):
            references.extend(item.get("evidenceIds", []))
    for item in report.get("hypotheses", []):
        references += item.get("supportingEvidenceIds", []) + item.get("contradictingEvidenceIds", [])
    references += [item["evidenceId"] for item in report.get("similarCases", [])]
    for item in report.get("uncertainties", []):
        references += item.get("relatedEvidenceIds", [])
    missing = sorted(set(references) - valid_ids)
    if missing:
        errors.append(f"analysis-result.json: unknown evidence references {missing}")
    y = report.get("impact", {}).get("yield", {})
    expected = round(y.get("baselinePercent", 0) - y.get("observedPercent", 0), 6)
    if abs(expected - y.get("absoluteDropPercentagePoints", -1)) > 1e-6:
        errors.append("analysis-result.json: yield absolute drop is inconsistent")
    timeline = [item["occurredAt"] for item in report.get("timeline", [])]
    if timeline != sorted(timeline):
        errors.append("analysis-result.json: timeline is not sorted")

if jev_example:
    response = jev_example.get("response", {})
    if not jev_example.get("synthetic"):
        errors.append("jev-assessment.json: synthetic example must be labeled")
    for question_id, answer in response.get("answers", {}).items():
        probabilities = answer.get("probabilities", {})
        if probabilities and abs(sum(probabilities.values()) - 1.0) > 1e-6:
            errors.append(f"jev-assessment.json: probabilities for {question_id} do not sum to 1")
        if answer.get("type") in {"choice", "score"} and "confidence" not in answer:
            errors.append(f"jev-assessment.json: {question_id} lacks confidence")
        if answer.get("type") == "noul" and "confidence" in answer:
            errors.append(f"jev-assessment.json: Noul {question_id} must not carry confidence")

if tools and workflow and questions:
    tool_ids = {item["toolId"] for item in tools["tools"]}
    if any(item.get("capability") != "READ" for item in tools["tools"]):
        errors.append("tool-registry.json: V1 contains a non-READ tool")
    workflow_tools = {tool for phase in workflow["phases"] for tool in phase.get("requiredTools", [])}
    unknown_tools = sorted(workflow_tools - tool_ids)
    if unknown_tools:
        errors.append(f"workflow: unknown tools {unknown_tools}")
    workflow_questions = {q for phase in workflow["phases"] for q in ([phase["jevQuestion"]] if "jevQuestion" in phase else phase.get("jevQuestions", []))}
    unknown_questions = sorted(workflow_questions - set(questions["questions"]))
    if unknown_questions:
        errors.append(f"workflow: unknown Jev questions {unknown_questions}")

events_path = ROOT / "examples/sse-events.jsonl"
try:
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sequences = [event["sequence"] for event in events]
    if sequences != list(range(1, len(sequences) + 1)):
        errors.append("sse-events.jsonl: sequence must start at 1 and be contiguous")
    if len({event["taskId"] for event in events}) != 1:
        errors.append("sse-events.jsonl: all events must reference one task")
except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
    errors.append(f"sse-events.jsonl: {exc}")

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
for doc in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "agent").rglob("*.md")), *sorted((ROOT / "examples").rglob("*.md")), *sorted((ROOT / "scripts").rglob("*.md"))]:
    for link in link_pattern.findall(doc.read_text(encoding="utf-8")):
        target = link.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if not (doc.parent / target).resolve().exists():
            errors.append(f"{doc.relative_to(ROOT)}: broken link {link}")

if errors:
    print("Contract validation failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Contract validation passed: JSON Schema, references, workflow, SSE sequence, and Markdown links.")
