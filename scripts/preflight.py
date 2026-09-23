#!/usr/bin/env python3
"""Fail-closed deployment profile preflight without contacting external services."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "deploy" / "profiles"
PROFILES = {
    "mock-recorded": {"platform": "mock", "decision": "recorded"},
    "mock-live-jev": {"platform": "mock", "decision": "typesafe"},
    "platform-shadow": {"platform": "platform", "decision": "typesafe"},
    "platform-production": {"platform": "platform", "decision": "typesafe"},
}
PLACEHOLDER_HOSTS = {"platform.invalid.example", "jev.invalid.example"}
SENSITIVE_KEY = re.compile(r"(?:PASSWORD|SECRET|TOKEN|API_KEY|DATABASE_URL)$")


class PreflightError(ValueError):
    pass


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PreflightError(f"cannot read config file: {path}") from exc
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise PreflightError(f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise PreflightError(f"{path}:{number}: invalid or duplicate key")
        values[key] = value
    return values


def safe_label(key: str, value: str) -> str:
    return "<set>" if SENSITIVE_KEY.search(key) and value else value


def require_url(config: dict[str, str], key: str, *, allow_placeholder: bool) -> None:
    value = config.get(key, "")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PreflightError(f"{key} must be an HTTPS origin without credentials")
    if parsed.query or parsed.fragment:
        raise PreflightError(f"{key} must not contain query or fragment data")
    if not allow_placeholder and parsed.hostname in PLACEHOLDER_HOSTS:
        raise PreflightError(f"{key} still uses a synthetic placeholder host")


def validate(profile: str, config: dict[str, str], *, allow_placeholder: bool) -> list[str]:
    expected = PROFILES[profile]
    actual_profile = config.get("PE_AGENT_DEPLOY_PROFILE", profile)
    if actual_profile != profile:
        raise PreflightError("PE_AGENT_DEPLOY_PROFILE does not match --profile")
    if config.get("PE_AGENT_PLATFORM_PROFILE") != expected["platform"]:
        raise PreflightError("platform profile does not match selected deployment profile")
    if config.get("PE_AGENT_DECISION_PROFILE") != expected["decision"]:
        raise PreflightError("decision profile does not match selected deployment profile")
    if config.get("PE_AGENT_ARCHIVE_ENABLED", "false").lower() != "false":
        raise PreflightError("archive must remain disabled during preflight")

    checks = ["profile", "archive-default-off"]
    if expected["platform"] == "mock":
        scenario = config.get("PE_AGENT_MOCK_SCENARIO_PATH", "")
        if not scenario:
            raise PreflightError("mock profile requires PE_AGENT_MOCK_SCENARIO_PATH")
        checks.append("mock-scenario-configured")
    else:
        require_url(config, "PE_AGENT_PLATFORM_BASE_URL", allow_placeholder=allow_placeholder)
        checks.append("platform-origin-syntax")

    if expected["decision"] == "typesafe":
        require_url(config, "PE_AGENT_TYPESAFE_BASE_URL", allow_placeholder=allow_placeholder)
        if not config.get("PE_AGENT_TYPESAFE_API_KEY") and not allow_placeholder:
            raise PreflightError("PE_AGENT_TYPESAFE_API_KEY must be injected at runtime")
        checks.append("decision-origin-syntax")

    explanation_profile = config.get("PE_AGENT_EXPLANATION_PROFILE", "disabled")
    if explanation_profile not in {"disabled", "openai_compatible"}:
        raise PreflightError("PE_AGENT_EXPLANATION_PROFILE is invalid")
    if explanation_profile == "openai_compatible":
        require_url(config, "PE_AGENT_LLM_BASE_URL", allow_placeholder=allow_placeholder)
        if not config.get("PE_AGENT_LLM_MODEL", "").strip():
            raise PreflightError("PE_AGENT_LLM_MODEL must be configured")
        if not config.get("PE_AGENT_LLM_API_KEY") and not allow_placeholder:
            raise PreflightError("PE_AGENT_LLM_API_KEY must be injected at runtime")
        checks.append("llm-origin-syntax")

    if profile == "platform-production" and config.get("PE_AGENT_ENVIRONMENT") != "production":
        raise PreflightError("platform-production requires PE_AGENT_ENVIRONMENT=production")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="mock-recorded")
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--allow-synthetic-placeholders",
        action="store_true",
        help="validate checked-in templates without treating .invalid hosts as configured",
    )
    args = parser.parse_args()
    config_path = args.config or PROFILE_DIR / f"{args.profile}.env"
    try:
        config = load_env(config_path)
        config.update({key: value for key, value in os.environ.items() if key.startswith("PE_AGENT_")})
        checks = validate(args.profile, config, allow_placeholder=args.allow_synthetic_placeholders)
    except PreflightError as exc:
        print(f"preflight failed: {exc}", file=sys.stderr)
        return 1

    print(f"preflight passed: profile={args.profile}; checks={','.join(checks)}")
    visible = {
        key: safe_label(key, value)
        for key, value in config.items()
        if key in {"PE_AGENT_ENVIRONMENT", "PE_AGENT_PLATFORM_PROFILE", "PE_AGENT_DECISION_PROFILE"}
    }
    if visible:
        print("effective non-sensitive config: " + ", ".join(f"{key}={value}" for key, value in sorted(visible.items())))
    print("external connectivity was not attempted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
