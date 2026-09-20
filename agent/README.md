# Agent 声明式资产

本目录定义 V1 Runtime 的输入契约，不是可直接运行的 Agent 框架。

- `workflow/yield-drop.workflow.json`：固定阶段、预算和可用工具。
- `tools/tool-registry.json`：只读工具及参数边界。
- `schemas/analysis-report.schema.json`：前后端共享报告契约。
- `jev-questions.json`：TypeSafe Jev 的原子问题模板。
- `model-profile.json`：官方 API 能力快照和生产配置要求。
- `prompts/report-template.md`：确定性报告表达规则。

生产实现必须在代码中校验这些资产；读取 JSON 文件本身不构成安全边界。
