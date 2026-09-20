# Tool API Contract

## Example

`getSPCTrend`

Input:
```json
{
  "toolId": "ETCH01",
  "parameter": "PRESSURE",
  "startTime": "...",
  "endTime": "..."
}
```

Output:
```json
{
  "toolId": "ETCH01",
  "parameter": "PRESSURE",
  "points": [],
  "violations": []
}
```

## Tool Contract Requirements

- schema
- permission
- timeout
- retry
- idempotency
- audit
- source metadata
- version

## V3 Action Tool

Action Tool 额外要求：
- riskLevel
- approvalPolicy
- idempotencyKey
- rollbackStrategy
- verificationPlan
