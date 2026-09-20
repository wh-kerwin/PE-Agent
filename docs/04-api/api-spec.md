# Business API

## Create

POST `/api/ai/case-analysis`

Request:
```json
{
  "caseId": "CASE001",
  "mode": "INVESTIGATION"
}
```

Response:
```json
{
  "taskId": "AI-001",
  "status": "RUNNING"
}
```

## Get Task

GET `/api/ai/case-analysis/{taskId}`

## Stream

GET `/api/ai/case-analysis/{taskId}/stream`

## Feedback

POST `/api/ai/case-analysis/{taskId}/feedback`

## Retry

POST `/api/ai/case-analysis/{taskId}/retry`

## V3 Approval

POST `/api/ai/actions/{actionId}/approve`

POST `/api/ai/actions/{actionId}/reject`

## V3 Execution

POST `/api/ai/actions/{actionId}/execute`

实际执行必须再次经过权限和审批校验。
