# 2026-09-20 文档重整记录

依据 `docs/01-product/PRD-V1.md` 原稿和用户补充的 Dashboard 嵌入模式，重建 frontend/backend 之外的项目资料。

核心修正：把产品从泛化 Agent 平台收敛为现有 Case Table 的 AI 分析功能；V1 固定 Yield Drop 与只读工具；分离计算终态、人工复核和 Case Book 归档；统一 API/SSE/数据契约；补齐权限、重连、并发、部分结果和验收路径。

用户提供 [TypeSafe 官方文档](https://docs.typesafe.ai/)。核实 Jev 为 System One 模型，采用 state + Choice/Score/Noul，而非长文本生成或原生 Agent Tool Calling。设计因此调整为“Runtime 调查 + Jev 原子判断 + 代码校验/组装报告”。

原始 35 个非 frontend/backend 文件在重整前备份至被 `.gitignore` 排除的 `work/regeneration-20260920/before.zip`。`frontend/` 与 `backend/` 保持原状。`PRD-V0.md` 仅说明归档关系，不复制旧基线。
