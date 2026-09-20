# 可观测性

每任务关联 traceId / taskId / caseId；跨系统日志只保留授权的标识或哈希。Span：context.load、plan、tool.call、evidence.validate、model.generate、report.validate、report.persist、casebook.save。

| 指标 | 口径 |
|---|---|
| firstProgressMs | 点击到首个服务端真实阶段事件 |
| totalDurationMs | 接受任务到计算终态，包含排队 |
| toolDurationMs | 每次工具尝试耗时，按 toolId/status 聚合 |
| completionRate | COMPLETED / 已接受非用户取消任务 |
| partialRate / timeoutRate | PARTIAL_RESULT / TIMEOUT 分别计数，不计作完整成功 |
| invalidOutputRate | Schema 或语义校验失败次数 / 候选报告次数 |
| reconnectRecoveryRate | 成功续传或快照恢复 / 断线恢复尝试 |
| evidenceGrounding | 专家核实事实有正确证据支撑的比例 |

记录 modelId、adapterVersion、promptVersion、schemaVersion、toolRegistryVersion、tokenUsage、调用/重试次数和剩余预算。公开进度只包含阶段和安全摘要，不暴露内部思维链。

按模型与数据源监控 401/403、429、超时、输出无效、队列积压和 SSE 断线率。阈值需试点建立；超预算由运行时硬截止，不依赖告警。业务评价采用同类型 Case 的调查时长与工程师采纳情况，不能用 Helpful 等同根因准确率。
