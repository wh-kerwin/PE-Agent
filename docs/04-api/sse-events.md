# SSE Event Protocol

## Events

analysis_started
context_loading
context_loaded
plan_created
tool_call_started
tool_call_completed
evidence_created
finding_generated
correlation_generated
hypothesis_generated
recommendation_generated
report_generated
action_created
approval_required
action_executing
action_completed
verification_started
verification_completed
analysis_completed
analysis_failed

## Event Envelope

```json
{
  "eventId": "EVT001",
  "taskId": "AI001",
  "timestamp": "2026-09-20T09:00:00Z",
  "type": "finding_generated",
  "data": {}
}
```

## Reconnect

客户端保存 taskId + lastEventId。

后端任务状态必须持久化，不能只依赖 SSE 内存。
