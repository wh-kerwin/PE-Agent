# Case Analysis Business API V1

Base path：`/api/ai/case-analysis`。JSON 使用 camelCase，时间为 ISO 8601 UTC。身份来自宿主会话；请求体不接受 userId/tenantId/role。

## 创建或恢复分析

`POST /api/ai/case-analysis`

```json
{
  "caseId": "CASE-20260920-001",
  "caseVersion": "17",
  "idempotencyKey": "2adba7e8-7bd1-4650-aac4-a41d42726991"
}
```

成功返回 `202 Accepted`；同一授权范围、caseVersion 和幂等键返回同一任务。已有运行任务时可返回它并设置 `reused: true`。

```json
{
  "taskId": "ANA-20260920-001",
  "caseId": "CASE-20260920-001",
  "caseVersion": "17",
  "status": "CREATED",
  "reused": false,
  "streamUrl": "/api/ai/case-analysis/ANA-20260920-001/stream"
}
```

`409 CASE_VERSION_CONFLICT` 表示列表版本已过期，客户端刷新 Case 后由用户重试。`422 UNSUPPORTED_CASE_TYPE` 不创建任务。

## 查询任务

`GET /api/ai/case-analysis/{taskId}` 返回权威快照：任务状态、阶段、progress、可用报告、reviewStatus、warnings、版本和 timestamps。只要报告可用，即使状态为 PARTIAL_RESULT 也返回 report。

`GET /api/ai/case-analysis?caseId={caseId}&latest=true` 用于页面刷新恢复，按当前用户权限返回最新可见任务。

## 事件流

`GET /api/ai/case-analysis/{taskId}/stream`，响应 `text/event-stream`。客户端可发送 `Last-Event-ID`；服务端先回放未确认事件。回放窗口外返回 `409 EVENT_CURSOR_EXPIRED`，客户端改用 GET 快照并从返回的 latestEventId 重新连接。详见 [SSE](sse-events.md)。

## 人工复核

`POST /api/ai/case-analysis/{taskId}/review`

```json
{
  "reportVersion": 1,
  "reviewStatus": "CORRECTED",
  "helpful": true,
  "confirmedHypothesisId": null,
  "actualRootCause": "Chamber pressure sensor calibration drift",
  "comment": "Confirmed after calibration check.",
  "idempotencyKey": "f7235805-a2b4-4911-b27b-ac75aa39aab7"
}
```

`helpful` 可空且与 reviewStatus 独立。报告版本过期返回 409。修正内容作为新 review revision 保存，不修改 AI 报告。

## 归档 Case Book

`POST /api/ai/case-analysis/{taskId}/casebook`

要求已存在 CONFIRMED/CORRECTED/INCONCLUSIVE 复核，需 `casebook.write` 权限。请求携带 reviewRevision 和幂等键；响应包含 archiveId/status。归档失败可重试且不能重复创建记录。

## 控制任务

`POST /{taskId}/retry`：只允许 FAILED/TIMEOUT/PARTIAL_RESULT，创建新 taskId 并带 `supersedesTaskId`。

`POST /{taskId}/cancel`：尽力停止并返回当前终态；重复取消幂等。重新分析不会覆盖旧报告。

完整错误码见 [error-codes](error-codes.md)。所有 POST 使用宿主平台 CSRF/认证策略。
