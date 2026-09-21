#!/usr/bin/env python3
"""Static validation for deployment manifests; requires only PyYAML."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
PROFILES = {
    "mock-recorded": ("mock", "recorded"),
    "mock-live-jev": ("mock", "typesafe"),
    "platform-shadow": ("platform", "typesafe"),
    "platform-production": ("platform", "typesafe"),
}
SECRET_NAME_PATTERN = re.compile(r"(password|secret|token|api[_-]?key)", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"(?:invalid\.example|synthetic|replace-me|change-me)", re.IGNORECASE)


class ValidationError(ValueError):
    pass


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"{path}: invalid YAML: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        require("=" in line, f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        require(bool(key) and key not in result, f"{path}:{number}: invalid or duplicate key")
        result[key] = value
    return result


def validate_profiles() -> None:
    for profile, (platform, decision) in PROFILES.items():
        path = DEPLOY / "profiles" / f"{profile}.env"
        require(path.is_file(), f"missing profile file: {path}")
        values = parse_env_file(path)
        require(values.get("PE_AGENT_DEPLOY_PROFILE") == profile, f"{path}: profile mismatch")
        require(values.get("PE_AGENT_PLATFORM_PROFILE") == platform, f"{path}: platform mismatch")
        require(values.get("PE_AGENT_DECISION_PROFILE") == decision, f"{path}: decision mismatch")
        require(values.get("PE_AGENT_ARCHIVE_ENABLED", "").lower() == "false", f"{path}: archive must default off")
        for key, value in values.items():
            if SECRET_NAME_PATTERN.search(key) and value:
                require(
                    profile.startswith("mock-") and PLACEHOLDER_PATTERN.search(value) is not None,
                    f"{path}: secret-like value {key} must be runtime-injected",
                )


def validate_compose() -> None:
    path = DEPLOY / "compose.yaml"
    compose = load_yaml(path)
    services = compose.get("services", {})
    require(
        {"postgres", "migrate", "api", "worker", "frontend"} <= services.keys(),
        f"{path}: missing services",
    )
    require("alembic" in str(services["migrate"].get("command")), f"{path}: migration command missing")
    require("healthcheck" in services["api"], f"{path}: API healthcheck missing")
    require(services["api"].get("read_only") is True, f"{path}: API filesystem must be read-only")
    require(services["worker"].get("read_only") is True, f"{path}: worker filesystem must be read-only")
    serialized = path.read_text(encoding="utf-8")
    for profile in PROFILES:
        override = DEPLOY / f"compose.{profile}.yaml"
        require(override.is_file(), f"missing Compose override: {override}")
        require(profile in override.read_text(encoding="utf-8"), f"{override}: profile not explicit")
    require("PE_AGENT_ARCHIVE_ENABLED: ${PE_AGENT_ARCHIVE_ENABLED:-false}" in serialized, f"{path}: archive must default off")


def validate_helm() -> None:
    chart = DEPLOY / "helm" / "pe-agent"
    values = load_yaml(chart / "values.yaml")
    require("postgresql" not in values, "Helm chart must not provision PostgreSQL")
    require(values.get("externalDatabase", {}).get("secretName"), "external database secret reference required")
    require(values.get("config", {}).get("archiveEnabled") is False, "Helm archive must default off")
    templates = "\n".join(path.read_text(encoding="utf-8") for path in (chart / "templates").glob("*"))
    for token in (
        "kind: Deployment",
        "app.kubernetes.io/component: api",
        "app.kubernetes.io/component: worker",
        "kind: Job",
        "alembic",
        "kind: NetworkPolicy",
        "runAsNonRoot: true",
        "readOnlyRootFilesystem: true",
        "resources:",
        "livenessProbe:",
        "readinessProbe:",
        'nginx.ingress.kubernetes.io/proxy-buffering: "off"',
        "secretKeyRef:",
    ):
        require(token in templates, f"Helm templates missing required token: {token}")
    require("kind: Secret" not in templates, "Helm chart must not contain secret values")
    for profile in ("platform-shadow", "platform-production"):
        overlay = load_yaml(chart / f"values-{profile}.yaml")
        require(overlay.get("profile") == profile, f"Helm values missing explicit {profile}")
        require(overlay.get("config", {}).get("archiveEnabled") is False, f"{profile}: archive must default off")


def validate_dockerfile() -> None:
    backend_path = ROOT / "backend" / "Dockerfile"
    backend = backend_path.read_text(encoding="utf-8")
    require("USER 10001:10001" in backend, f"{backend_path}: runtime must be non-root")
    require("COPY --from=builder" in backend, f"{backend_path}: multi-stage build required")
    require("COPY ." not in backend, f"{backend_path}: broad context copy is not allowed")

    frontend_path = ROOT / "frontend" / "Dockerfile"
    frontend = frontend_path.read_text(encoding="utf-8")
    require("USER 101:101" in frontend, f"{frontend_path}: runtime must be non-root")
    require("COPY --from=builder" in frontend, f"{frontend_path}: multi-stage build required")
    require("COPY ." not in frontend, f"{frontend_path}: broad context copy is not allowed")


def validate_all() -> None:
    validate_profiles()
    validate_compose()
    validate_helm()
    validate_dockerfile()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        validate_all()
    except (OSError, ValidationError) as exc:
        print(f"deployment validation failed: {exc}", file=sys.stderr)
        return 1
    print("deployment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
