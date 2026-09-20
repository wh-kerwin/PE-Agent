# Manufacturing Tool Contract

工具是 Runtime 内部适配器，不向浏览器或 Jev 暴露 endpoint。统一调用对象：

```json
{
  "toolCallId": "TC-001",
  "taskId": "ANA-20260920-001",
  "toolId": "get_spc_evidence",
  "arguments": {"toolId":"ETCH01","parameter":"CHAMBER_PRESSURE","startAt":"2026-09-20T00:00:00Z","endAt":"2026-09-20T02:30:00Z"},
  "deadlineAt": "2026-09-20T01:03:18Z"
}
```

统一结果含 `status`（SUCCEEDED/PARTIAL/FAILED）、`data`、`source`（system、recordIds、adapterVersion）、`quality`（completeness、warnings）、`retrievedAt` 和 error。原始数据可存安全引用，不必复制到模型上下文。

适配器必须校验输入 Schema、授权实体、最大时间窗、行数/点数、单位、时区、数据版本和超时。读取工具幂等；一次可重试的网络错误最多自动重试一次。缓存键包含 tenant/permissionScopeHash/toolId/args/sourceVersion，撤权后不可复用。

Registry 中 `capability: READ` 是硬约束。任何生产写端点即使下游存在，也不得加入 V1 Registry。
