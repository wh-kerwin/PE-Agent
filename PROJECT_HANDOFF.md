# PE Agent 项目交接单

> 新会话只需先读取本文件即可恢复项目上下文。完成任何任务后，必须同步更新本文件的“当前状态”“验证记录”和“下一步待办”，再提交代码。

## 当前定位

- 项目：嵌入 PE Duty / Engineer Platform Dashboard 的 AI Case 分析功能。
- 新会话操作指南：[CLAUDE.md](CLAUDE.md)；新会话先读取本文件，再按该指南执行命令和架构约定。
- 当前分支：`main`。
- 当前基线提交：`4d06013`（mock-first vertical slice 与仓库指导已同步到 main）。
- 目标：完成 mock-first vertical slice 后，按外部输入和生产验收条件逐步推进真实集成。
- 当前实现只证明契约、流程和部署形状，不代表生产就绪。

## 已完成

- FastAPI API、Vue 分析抽屉、合成 Case 场景和 mock-recorded 演示 profile。
- PostgreSQL 任务、事件、outbox、报告、review、archive 模型及 Alembic migration。
- Worker lease/fence、CAS finalization、取消、重试、事件持久化和基础恢复能力。
- Mock platform adapters、Evidence 规范化、报告 Schema 与语义校验。
- Recorded Jev Choice / Score / Noul 决策契约；live TypeSafe smoke 仅显式 opt-in；Jev 配置使用独立的 `PE_AGENT_TYPESAFE_BASE_URL` 与运行时 `PE_AGENT_TYPESAFE_API_KEY`。
- 可选 OpenAI-compatible 表达层：独立 `ExplanationPort`、受限非流式 chat-completions adapter、`expression` 非权威命名空间；默认 disabled，不作为 Jev fallback。
- Mock 演示 Case 的 canonical 标识统一为 `SYN-CASE-PRESSURE-001` / version `1`；前端 Demo、E2E、smoke 默认值与后端 scenario/recording 一致。`mock-live-jev` API smoke 已用该 Case 返回 `202` 并创建任务。
- Engineer Review：报告版本校验、任务级幂等、revision、假设引用验证。
- Case Book：仅 mock archive；默认关闭；production 或真实 platform profile 开启会启动失败。
- SSE：字符串 cursor、有限 replay、heartbeat、terminal close、周期性身份复核。
- 安全边界：RequestScope 来自验证身份；scope hash 服务端派生；禁止从 Case 数据扩张授权范围；production 无身份适配器时 fail-closed。
- Compose、Helm、非 root 容器、CI、preflight、contract validation、deployment validation。
- PostgreSQL 生命周期 CHECK 约束及并发/租约/回滚集成测试。
- 工程师复核表单 hydration、任务切换、report 切换和状态相关字段提交边界。
- TODO 细项同步维护于 [docs/07-development/todo.md](docs/07-development/todo.md)。

## 最近验证

最近一次完整后端验证：

- `146 passed, 16 skipped`；跳过的是 Docker 不可用时的 PostgreSQL 集成测试和默认关闭的 live TypeSafe smoke。
- Ruff 通过。
- strict mypy 通过，49 个源文件。
- Contract validation 通过。
- Deployment validation 通过。
- `preflight.py --profile mock-recorded --allow-synthetic-placeholders` 通过。
- Docker Compose 合并配置及 `mock-live-jev` image build/up 通过：PostgreSQL healthy、migration Exited (0)、API healthy、Worker running、Frontend running；前端 `/` 返回 200，API `/health/live` 返回 `{"status":"ok"}`。
- Frontend Nginx 以非 root 用户和只读文件系统运行；`/var/cache/nginx`、`/var/run`、`/tmp` 使用 UID/GID 101 的 tmpfs。基础镜像关于 `user` directive 的 warning 不影响运行。
- `git diff --check` 通过。

已知环境限制：前端 `pnpm install` 后，`vue-tsc`、8 个前端 unit test、production build 和 3 个 Playwright E2E 均通过；Compose `mock-live-jev` 实机 build/up、前端 Nginx 和 API 健康检查也已通过。gstack 浏览器因独立 headless shell 路径缺失未能启动，浏览器流程已由 Playwright E2E 覆盖；Helm CLI 和本轮 PostgreSQL 集成测试仍未执行或受环境限制。

## 必须遵守的约束

- 不使用生产凭据或客户数据。
- 所有 fixture 和录制模型响应必须包含 `synthetic: true`。
- 不猜测客户 API 字段；真实平台接入前必须有官方文档和脱敏 payload。
- production profile 缺少适配器时必须启动失败，绝不回落到 mock。
- manufacturing integrations 只读。
- Jev 不选择 URL、凭据、身份或直接调用客户平台。
- live TypeSafe 测试必须 opt-in，普通 CI 不运行。
- preflight/smoke 不打印 token 或制造 payload。
- Case Book archive 默认关闭；mock success 不得表述为 production readiness。
- 复核的 `CONFIRMED` 必须有 `confirmedHypothesisId`；`CORRECTED` 必须有实际根因。
- 任何跨租户、跨 permission scope、未授权 entity 的访问都必须不可区分地失败或 fail-closed。

## 下一步待办

按优先级继续：

1. 已完成前端依赖安装后的 typecheck、unit test、build、Playwright E2E，以及 Compose mock-live-jev build/up 和 Nginx/API 健康检查；待 gstack/headed 浏览器工具可用时补充视觉验收。
2. 有 Helm CLI 时运行 lint/template；做 clean-checkout smoke test。
3. 完成 OpenAI-compatible 表达层的企业出域/质量/容量评审，取得真实 Jev 与 LLM 的合规批准和运行凭据；当前功能仍默认关闭，不代表生产可用。
4. 获取并记录宿主 Case API、SSO/IAM、Lot/Wafer/Tool/Recipe/SPC/FDC、历史 Case/Case Book 的官方资料和脱敏样例。
5. 在资料齐全后实现真实平台只读 adapters、身份集成和真实 Case Book adapter；先走 `platform-shadow`、archive disabled 和 golden Case 对比。
6. 持久化 tool execution 审计、normalized Evidence、model assessment 元数据；评估 lease renewal/checkpoint resume、SIGTERM 和已安装 wheel 运行。
7. 扩展 golden set、CJK、故障、越权、负载和 shadow pilot 验收。

完整外部输入和生产晋级条件见：

- [docs/07-development/todo.md](docs/07-development/todo.md)
- [docs/integration/known-limitations.md](docs/integration/known-limitations.md)
- [docs/integration/fde-runbook.md](docs/integration/fde-runbook.md)
- [docs/integration/production-readiness-checklist.md](docs/integration/production-readiness-checklist.md)
- [docs/integration/platform-discovery-checklist.md](docs/integration/platform-discovery-checklist.md)

## 完成任务时的固定流程

1. 先读本文件并检查 `git status`、当前分支和远端 tracking。
2. 只实现当前待办所需范围，不把 mock 结果升级表述为生产能力。
3. 运行与改动相关的测试；条件允许时运行完整后端、contract 和 deployment 验证。
4. 更新本文件：已完成、验证结果、限制和下一步待办；同步更新 `docs/07-development/todo.md`。
5. 检查 diff、敏感信息和 `git diff --check`。
6. 创建新 commit；除非用户明确要求，不 amend、不 force-push。
7. 向用户报告修改、测试、阻塞和剩余待办。
