from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILES = {
    "reportSchema": ROOT / "agent/schemas/analysis-report.schema.json",
    "workflow": ROOT / "agent/workflow/yield-drop.workflow.json",
    "questions": ROOT / "agent/jev-questions.json",
    "tools": ROOT / "agent/tools/tool-registry.json",
    "modelProfile": ROOT / "agent/model-profile.json",
}
ALLOWED_PROFILES = {
    "mock-recorded",
    "mock-live-jev",
    "platform-shadow",
    "platform-production",
}


def git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def file_evidence(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    payload = json.loads(data)
    version = (
        payload.get("schemaVersion")
        or payload.get("version")
        or payload.get("workflowId")
        or "declared-in-content"
    )
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "version": version,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_evidence(
    profile: str,
    image_digests: list[str],
    test_summaries: list[str],
) -> dict[str, Any]:
    if profile not in ALLOWED_PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    for digest in image_digests:
        if not digest.startswith("sha256:"):
            raise ValueError("image digests must use sha256:<digest>")
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "gitSha": git_sha(),
        "deploymentProfile": profile,
        "contracts": {name: file_evidence(path) for name, path in VERSION_FILES.items()},
        "imageDigests": sorted(image_digests),
        "testSummaries": sorted(test_summaries),
        "resolvedTestModel": "jev-1.13.0" if profile.startswith("mock-") else None,
        "synthetic": profile.startswith("mock-"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate non-sensitive release evidence")
    parser.add_argument("--profile", choices=sorted(ALLOWED_PROFILES), required=True)
    parser.add_argument("--image-digest", action="append", default=[])
    parser.add_argument("--test-summary", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.profile, args.image_digest, args.test_summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Release evidence written to {args.output}")


if __name__ == "__main__":
    main()
