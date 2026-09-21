# Platform Field Mapping Template

Create one reviewed table per source contract. Values below are synthetic placeholders, not production endpoint or credential examples.

## Contract metadata

| Item | Value |
|---|---|
| Source/owner | `<source-name>` / `<owner-role>` |
| Contract/version | `<approved-version>` |
| Base origin | `<runtime-config-key; do not record the URL here>` |
| Authentication | `<delegated-scope>` |
| Authorization resource | `<case/lot/tool resource expression>` |
| Timeout/rate limit | `<seconds>` / `<requests-per-window>` |
| Data classification/residency | `<classification>` / `<region>` |
| Retention/deletion | `<policy reference>` |

## Field mapping

| Domain field | Source path | Type | Required | Timezone/unit | Transformation/validation | Redaction | Example |
|---|---|---|---|---|---|---|---|
| `caseId` | `<path>` | string | yes | n/a | non-empty, stable ID | none | `CASE-SYNTHETIC-001` |
| `caseVersion` | `<path>` | string | yes | n/a | immutable snapshot/version token | none | `17` |
| `caseType` | `<path>` | enum | yes | n/a | map only approved Yield Drop value to `YIELD_DROP` | none | `YIELD_DROP` |
| `createdAt` | `<path>` | timestamp | yes | UTC | parse offset-aware ISO 8601; reject ambiguity | policy | `2026-09-20T01:35:00Z` |
| `lotIds[]` | `<path>` | string[] | yes | n/a | deduplicate; authorize each entity | policy | `LOT-SYNTHETIC-001` |
| `symptom.observedYieldPercent` | `<path>` | number | yes | percent | range 0–100; no ratio/percent guessing | none | `82.0` |

Add rows for Tool, Recipe, Wafer, SPC/FDC parameter, record ID, source version, quality, and raw-reference fields. Never put secrets, tokens, real customer identifiers, or internal hostnames in this document.

## Error mapping

| Source condition | Adapter/domain result | Retryable | Safe operator detail |
|---|---|---:|---|
| Unauthenticated/expired delegation | `AUTHENTICATION_REQUIRED` | no | re-authenticate through host |
| Entity outside authorized scope | `PERMISSION_DENIED` / `CASE_ACCESS_DENIED` | no | permission denied |
| Snapshot changed | `VERSION_CONFLICT` / `CASE_VERSION_CONFLICT` | no | refresh Case |
| Deadline exceeded | `TIMEOUT` | policy | source timed out |
| Partial rows/points | `PARTIAL` with completeness/warnings | policy | approved omission summary |
| Dependency unavailable | `UNAVAILABLE` | yes | source unavailable |
| Unmapped source response | fail closed | no | contract mapping missing |

Do not copy downstream response bodies or stack traces into browser errors.

## Semantics and verification

- Primary key and snapshot/version semantics: `<decision>`
- Pagination/order/deduplication: `<decision>`
- Timestamp precision and daylight-saving behavior: `<decision>`
- Unit vocabulary and approved conversions: `<decision>`
- Missing/null/zero/out-of-range handling: `<decision>`
- Maximum time window and row/point cap: `<decision>`
- Source record ID and fixed deep-link route: `<decision>`
- Cache key, permission-scope hash, source version, and revocation invalidation: `<decision>`
- Approved synthetic/redacted fixtures and owner sign-off reference: `<decision>`
