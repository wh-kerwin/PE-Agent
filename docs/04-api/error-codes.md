# 错误码

错误格式：`{"error":{"code":"...","message":"...","retryable":false,"traceId":"...","details":{}}}`。message 可展示但不包含内部堆栈或敏感源响应。

| HTTP | code | 客户端行为 |
|---:|---|---|
| 400 | INVALID_REQUEST | 修正请求，不重试 |
| 401 | AUTHENTICATION_REQUIRED | 进入宿主登录恢复流程 |
| 403 | CASE_ACCESS_DENIED | 关闭数据视图；不自动重试 |
| 404 | TASK_NOT_FOUND | 返回列表并刷新任务引用 |
| 409 | CASE_VERSION_CONFLICT | 刷新 Case，由用户重新分析 |
| 409 | EVENT_CURSOR_EXPIRED | GET 快照后重新订阅 |
| 409 | REPORT_VERSION_CONFLICT | 刷新报告再提交复核 |
| 422 | UNSUPPORTED_CASE_TYPE | 显示 V1 仅支持 Yield Drop |
| 422 | INVALID_MODEL_OUTPUT | 不展示候选报告，可按策略重试一次 |
| 429 | RATE_LIMITED | 按 Retry-After 退避 |
| 502 | TOOL_UNAVAILABLE | Worker 决定部分结果/失败 |
| 503 | MODEL_UNAVAILABLE | 确定性流程或 PARTIAL_RESULT |
| 504 | ANALYSIS_TIMEOUT | 显示已有结果并允许重试 |

工具内部错误映射为受控 code 并进入审计；不能把下游返回正文直接传浏览器。
