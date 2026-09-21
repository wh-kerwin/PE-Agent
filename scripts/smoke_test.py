#!/usr/bin/env python3
"""Non-destructive HTTP smoke checks for an already running PE Agent API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class SmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict[str, Any]:
        try:
            value = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeError("response was not valid JSON") from exc
        if not isinstance(value, dict):
            raise SmokeError("response JSON must be an object")
        return value


def request(base_url: str, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 10.0) -> Response:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return Response(response.status, dict(response.headers.items()), response.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, dict(exc.headers.items()), exc.read())
    except urllib.error.URLError as exc:
        raise SmokeError(f"request failed for {path}: {exc.reason}") from exc


def health_check(base_url: str, timeout: float) -> None:
    response = request(base_url, "/health/live", timeout=timeout)
    if response.status != 200 or response.json().get("status") != "ok":
        raise SmokeError(f"liveness check failed with HTTP {response.status}")
    print("PASS liveness")


def analysis_check(base_url: str, case_id: str, case_version: str, timeout: float) -> None:
    response = request(
        base_url,
        "/api/ai/case-analysis",
        method="POST",
        payload={
            "caseId": case_id,
            "caseVersion": case_version,
            "idempotencyKey": "00000000-0000-4000-8000-000000000001",
        },
        timeout=timeout,
    )
    if response.status != 202:
        raise SmokeError(f"analysis submission failed with HTTP {response.status}")
    body = response.json()
    if not body.get("taskId") or body.get("caseId") != case_id:
        raise SmokeError("analysis response omitted expected identifiers")
    print(f"PASS analysis accepted taskId={body['taskId']}")
    print("SKIP archive (disabled by default and never invoked by this smoke script)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--analysis", action="store_true", help="create an idempotent synthetic analysis task")
    parser.add_argument("--case-id", default="CASE-20260920-001")
    parser.add_argument("--case-version", default="17")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        print("smoke failed: --base-url must be an HTTP(S) origin without credentials", file=sys.stderr)
        return 2
    try:
        health_check(args.base_url, args.timeout)
        if args.analysis:
            analysis_check(args.base_url, args.case_id, args.case_version, args.timeout)
        else:
            print("SKIP analysis (enable explicitly with --analysis)")
            print("SKIP archive (disabled by default and never invoked by this smoke script)")
    except SmokeError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
