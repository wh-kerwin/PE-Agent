# typeSafe Jev 候选模型接入

## 核实状态（2026-09-20）

用户提及「最近发布的 typeSafe 的 Jev 模型」。当前没有可确认的官方链接、准确模型 ID 或 API 文档。AutoGLM 搜索因本地鉴权服务 HTTP 502 失败；直接网页搜索连接超时。这只能说明本次未能核实，不能据此判断该模型不存在。

因此本项目使用内部候选标识 `jev-candidate`，不把它当成厂商正式模型名。没有宣称支持原生 Tool Calling、结构化输出、流式输出、多模态、特定上下文长度、价格或私有部署。配置默认禁用，详见 [候选配置](../../agent/model-profile.json)。

## 为什么仍能推进

Dashboard 点击发起的是业务任务，不直接调用 Jev。Model Adapter 将规范化消息、工具描述和输出约束转换成真实厂商协议，Agent 与 UI 的业务契约保持一致。这里的类型安全是工程侧 JSON Schema 与运行时校验，不等于对 TypeSafe 厂商能力的声明。

| 适配器操作 | 输入 | 输出 |
|---|---|---|
| inspectCapabilities | 已核实配置 | tools、structuredOutput、streaming、limits 的已验证能力 |
| generate | messages、可选 tools/outputSchema、budget、deadline | text/toolCalls、finishReason、usage、modelId、requestId |
| cancel | requestId | 尽力取消；运行时仍忽略终态后的迟到结果 |

工具调用无论原生还是经受限 JSON 计划解析，都经过工具名、参数 Schema、权限、实体范围、预算校验。无原生工具能力时可由固定工作流取数，再让模型整理证据。无原生 JSON Schema 能力时解析 JSON 后严格校验，最多一次修复；仍失败则不发布报告。无模型 token streaming 时，业务 SSE 仍可推送运行时阶段与工具事件。

## 启用清单

需要记录官方资料 URL 与版本/日期、厂商/模型准确 ID、endpoint 与认证方式、数据留存/训练政策和地域、可用工具/输出能力、限额、超时/取消语义和计费口径。密钥通过服务端 Secret 注入，不提交仓库。

接入契约测试覆盖：普通生成、有效工具调用、未知工具、参数越界、非法 JSON、幻觉证据 ID、超时、429、5xx、取消、用量。使用相同黄金 Case 比较证据准确性、时延和成本，达标后启用。

模型切换必须符合相同数据出域政策并记录版本；不能静默回退到未批准供应商。无可用模型返回 MODEL_UNAVAILABLE，mock 只能用于清楚标识的开发环境。
