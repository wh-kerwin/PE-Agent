# SSE 事件协议 V1

SSE 是进度提示与增量通知，GET 任务快照是权威状态。每条事件使用标准 `id`、`event`、`data`：

```text
id: 42
event: phase_changed
data: {"schemaVersion":"1.0.0","taskId":"ANA-20260920-001","sequence":42,"occurredAt":"2026-09-20T01:03:10Z","payload":{"phase":"INVESTIGATING","message":"Checking SPC evidence"}}
```

允许事件：`analysis_started`、`phase_changed`、`tool_started`、`tool_completed`、`tool_failed`、`evidence_added`、`report_generated`、`analysis_completed`、`analysis_partial`、`analysis_failed`、`analysis_cancelled`、`heartbeat`。

事件 sequence 对任务严格递增。客户端按 `(taskId, sequence)` 去重，忽略旧序号；不要根据到达次数累计进度。payload 只包含 UI 所需安全摘要，不发送工具凭据、原始敏感数据或思维链。

`tool_failed` 不必结束任务；是否转 PARTIAL_RESULT 由最终快照决定。`report_generated` 只携带 reportVersion 和 GET URL，不在 SSE 复制完整报告。终态事件之后服务端关闭流。

重连使用 `Last-Event-ID`。心跳建议每 15 秒发送 comment 或 heartbeat；代理禁用缓冲。网络错误采用带 jitter 的退避，页面可见且任务未终态时重连。401/403 停止重连；cursor 过期先 GET 快照。任务在无 SSE 订阅时继续运行。
