# Agent 架构

一个 AnalysisTask 对应一个有预算的调查实例。V1 使用单 Agent 与专用工具。

| 模块 | 输入 | 输出与约束 |
|---|---|---|
| Context Builder | caseId + 可信身份 | 带 caseVersion 的权限内快照与时间窗 |
| Planner | 上下文、已有证据、剩余预算 | 白名单工具的计划；依赖顺序与查询范围可校验 |
| Tool Router | 已校验调用 | 有来源的工具结果或结构化错误 |
| Evidence Engine | 工具结果 | Evidence ID、单位/时间检查、来源与可信状态 |
| Analyzer | 证据与对照 | 发现、关联、假设、反证、建议 |
| Report Validator | 模型候选报告 | Schema 校验 + 引用/实体/数值/权限校验 |
| Persistence | 当前阶段、有效结果 | 任务快照、不可变报告、SSE outbox |

循环：Plan → Validate → Execute → Observe → Evidence → Re-plan 或 Report。工具总数、并发、轮数、输出 tokens 与截止时间由运行时强制。模型超预算、未知工具和越界实体请求均不能执行。

工作流见 [调查流程](../03-agent/investigation-workflow.md)。工具配置、工作流和提示词位于 [agent](../../agent/README.md)，它们是实施输入，尚不是可运行框架。

报告生成和审查分离；模型不生成 reviewStatus、审批、归档成功状态或宿主 Case 最终状态。
