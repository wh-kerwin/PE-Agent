# PE Case Analysis Agent

嵌入 PE Duty / Engineer Platform Dashboard 的 **AI Case 分析功能**。工程师在现有 Case List / Table 行末点击「AI 分析」，分析抽屉随即打开，展示调查进度、证据、根因假设与处置建议；工程师确认后可将结果归档至 Case Book。

---

## 解决什么问题

在半导体制造中，Yield Drop（良率下降）是 PE Duty 工程师最频繁处理的异常类型之一。传统流程要求工程师逐一查看 Lot、Wafer、设备、配方、SPC/FDC 等数据源，人工判断根因，整个过程往往耗时 30 分钟以上。

本项目的目标是将这个过程压缩到 10 分钟量级：工程师点击一个按钮，Agent 自动调查相关制造数据，形成结构化报告，工程师做最终判断。**工程师始终是最终决策者**；Agent 提供关联证据和假设，不替代人类判断，不执行任何生产写操作。

---

## 产品边界

**V1 包含：**
- 单类型场景：Yield Drop
- 只读工具：Lot / Wafer / Tool / Recipe / SPC / FDC / 历史 Case 上下文
- 可恢复 SSE 实时进度；刷新、关闭抽屉不取消后台任务
- 结构化报告（Case Summary、影响范围、时间线、关键发现、证据、相关性分析、根因假设、历史相似案例、建议、不确定性）
- 工程师复核（CONFIRMED / CORRECTED / INCONCLUSIVE）与 Case Book 归档（默认关闭）

**V1 不包含（路线图）：**
- V2：多类型 Case、交互式调查、知识库治理
- V3：审批后受控动作（Hold/Release Lot、修改 Recipe 等写操作）

详见 [PRD-V1](docs/01-product/PRD-V1.md)、[PRD-V2](docs/01-product/PRD-V2.md)、[PRD-V3](docs/01-product/PRD-V3.md)。

---

## 用户旅程

| 步骤 | 工程师 | 系统 |
|---|---|---|
| 发现 | 在 Dashboard 筛选 Case | 保留列表筛选/排序/分页/滚动位置 |
| 触发 | 点击行末「AI 分析」 | 立即打开抽屉，提交 caseId（无需写问题） |
| 等待 | 查看调查进度 | SSE 推送已完成/进行中/失败的查询阶段 |
| 检查 | 阅读发现、时间线、假设 | 每项可展开证据与来源；缺数据显著提示 |
| 复核 | 接受 / 修正 / 标为待调查 | 保存独立 reviewStatus；Helpful ≠ 根因确认 |
| 归档 | 点击保存 Case Book | 保存报告版本与人工结论；失败可重试 |
| 返回 | 关闭抽屉，继续其他 Case | 后台任务不取消；列表保留原状态 |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│  宿主 Dashboard（PE Duty / Engineer Platform）                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Vue / Pinia 分析抽屉（frontend/）                      │  │
│  │  · CaseAnalysisDrawer.vue  · EngineerReviewForm.vue      │  │
│  │  · caseAnalysis.ts（状态边界：缓存/SSE/恢复/终态）      │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└───────────────────────────────┼──────────────────────────────────┘
                                │ HTTP / SSE
┌───────────────────────────────▼──────────────────────────────────┐
│  FastAPI 服务（backend/src/pe_agent/）                           │
│  · routes/analysis.py — 任务/报告/复核/归档/SSE 路由            │
│  · task_service.py — 事务边界、幂等、可见性规则                 │
│  · yield_drop_workflow.py — 只读平台调用编排                    │
│  · reporting.py — 报告组装 + JSON Schema / 语义校验             │
└───────────────────────────┬──────────────────────────────────────┘
                            │ 异步任务
┌──────────────────────────────▼───────────────────────────────────┐
│  Worker（backend/src/pe_agent/worker/）                         │
│  · 租约/fence 感知协调器 · checkpoint 恢复 · SIGTERM 优雅停机  │
│  · 通过 PlatformDataPort 调用只读制造数据适配器                  │
│  · 通过 DecisionPort 调用 Jev（Choice/Score/Noul）              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
        ┌──────────────────┼─────────────────────┐
        │                  │                     │
┌───────▼──────────┐ ┌────▼────────────────┐ ┌──▼──────────────────┐
│ PostgreSQL        │ │ TypeSafe Jev /      │ │ OpenAI-compat 表达层│
│ · task/events     │ │ OpenAI LLM（可选）  │ │ （默认关闭）        │
│ · outbox/report   │ │ · PE_AGENT_TYPESAFE_* │ · 非权威 expression │
│ · review/archive  │ │ · live smoke opt-in  │ │ · 不改 canonical 报告│
│ · audit tables ×3 │ └─────────────────────┘ └─────────────────────┘
│ · checkpoint      │
└────────────────────┘
```

### 关键设计原则

- **只读边界**：Jev 和 LLM 均不选择 URL/凭据/身份，不直接调用客户平台；所有数据读取经 `PlatformDataPort` 走验证身份
- **合成优先**：Mock 适配器产出确定性合成数据；所有 fixture 均带 `synthetic: true`；mock 成功 ≠ 生产就绪
- **fail-closed**：生产 profile 缺少适配器配置时启动失败，绝不回落到 mock；跨租户/越权访问统一不可区分地失败
- **SSE 可重放**：带字符串 cursor、有限重放窗口、heartbeat、终态关闭；刷新后从 lastEventId 续传

---

## 目录结构

```
backend/
├── src/pe_agent/
│   ├── main.py                # FastAPI app、engine、settings、错误处理、健康检查
│   ├── api/
│   │   ├── routes/analysis.py # 任务/报告/复核/归档/SSE 路由
│   │   ├── schemas.py        # Pydantic wire schemas
│   │   └── dependencies.py   # 身份归一化与权限校验
│   ├── application/
│   │   ├── task_service.py    # 事务边界、幂等、review/archive 规则
│   │   ├── yield_drop_workflow.py  # 只读平台调用编排
│   │   └── reporting.py       # 报告组装 + Schema/语义校验
│   ├── domain/               # 内部领域模型（不镜像客户原始 dict）
│   ├── ports/                # 平台/决策/CaseBook 端口接口
│   ├── adapters/
│   │   ├── mock_platform.py   # 确定性合成平台适配器
│   │   ├── decisions/         # recorded / typesafe Jev 决策
│   │   ├── explanations/      # OpenAI-compatible 表达层（默认关闭）
│   │   └── persistence/       # SQLAlchemy models + repositories
│   └── worker/service.py     # 租约/fence 协调器 + checkpoint 恢复
├── alembic/                  # 数据库迁移（0001 基础表 + 0002 checkpoint）
└── tests/

frontend/
└── src/
    ├── store/caseAnalysis.ts # 状态边界（缓存/SSE/恢复/终态）
    ├── components/
    │   ├── CaseAnalysisDrawer.vue
    │   └── EngineerReviewForm.vue
    ├── api/client.ts         # HTTP/SSE wire 契约
    └── types.ts              # 宿主中立的 client/host 接口

agent/
├── README.md                 # Agent 资产说明
├── schemas/
│   └── analysis-report.schema.json  # 报告 JSON Schema
└── jev-questions.json        # Jev 问题定义

deploy/
├── compose.yaml              # PostgreSQL + migration + API + worker + frontend
├── compose.mock-recorded.yaml # 默认 demo profile
├── compose.mock-live-jev.yaml # 启用 live Jev 的 profile
├── profiles/                 # 各 profile 环境变量
└── helm/pe-agent/            # Kubernetes Helm chart

scripts/
├── validate_contracts.py     # Schema/样例/引用/SSE/文档链接校验
├── validate_deploy.py        # 部署配置不变量校验
├── preflight.py              # profile 预检（`--profile mock-recorded`）
└── smoke_test.py             # 只读端到端 smoke test

docs/
├── 01-product/               # PRD V0/V1/V2/V3 + 用户旅程
├── 02-architecture/          # 系统架构 + 模型集成
├── 03-agent/                 # Agent 设计
├── 04-api/                   # API 规范 + SSE 事件协议
├── 05-data/                  # 数据模型
├── 06-frontend/              # 前端 UI 设计
├── 07-development/           # 开发计划 / 验收 / todo
├── integration/              # demo 脚本 / 已知限制 / FDE Runbook / 生产就绪清单
└── plans/                    # 实施计划
```

---

## 一键合成演示

默认 profile 为 `mock-recorded`，不调用客户平台或 live Jev。需要 Docker Compose：

```sh
docker compose \
  --env-file deploy/profiles/mock-recorded.env \
  -f deploy/compose.yaml \
  -f deploy/compose.mock-recorded.yaml \
  up --build
```

启动后：
- 前端：`http://localhost:4173`
- 或执行只读 smoke test：

```sh
python scripts/smoke_test.py --base-url http://localhost:8000 \
  --case-id SYN-CASE-PRESSURE-001 --case-version 1
```

完整演示流程、失败场景和清理命令见 [demo-script](docs/integration/demo-script.md)。生产集成前必须阅读 [known-limitations](docs/integration/known-limitations.md) 和 [FDE Runbook](docs/integration/fde-runbook.md)。

---

## 本地开发

### 安装依赖

```sh
python -m pip install -r scripts/requirements.txt
python -m pip install -e "backend[dev]"
npm ci --prefix frontend
```

### 运行测试与校验

```sh
# 后端
python -m pytest -c backend/pyproject.toml backend/tests
python -m ruff check backend/src backend/tests scripts
python -m mypy --config-file backend/pyproject.toml backend/src
python scripts/validate_contracts.py
python scripts/validate_deploy.py

# 前端
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm --prefix frontend run build

# 预检（mock-recorded profile）
python scripts/preflight.py --profile mock-recorded
```

### 注意事项

- PostgreSQL 集成测试需要 Docker；Docker 不可用时自动跳过
- Live TypeSafe smoke 默认关闭；仅当 `PE_AGENT_RUN_TYPESAFE_LIVE=1` + `PE_AGENT_TYPESAFE_BASE_URL` + `PE_AGENT_TYPESAFE_API_KEY` 全部设置时运行
- 不要把真实 key 写入 Compose profile、Helm values、镜像、日志或 shell 历史
- 生产 profile 缺少平台适配器配置时启动失败，**绝不回落到 mock**

---

## 相关文档

| 内容 | 入口 |
|---|---|
| V1 产品基线 | [PRD-V1](docs/01-product/PRD-V1.md) |
| 用户交互 | [用户旅程](docs/01-product/user-journey.md)、[Drawer 设计](docs/06-frontend/ui-design.md) |
| 系统架构 | [system-architecture](docs/02-architecture/system-architecture.md) |
| Jev 接入边界 | [model-integration](docs/02-architecture/model-integration.md) |
| Agent 设计 | [agent-design](docs/03-agent/agent-design.md)、[agent/](agent/README.md) |
| API / SSE | [api-spec](docs/04-api/api-spec.md)、[sse-events](docs/04-api/sse-events.md) |
| 数据契约 | [报告 Schema](agent/schemas/analysis-report.schema.json)、[数据模型](docs/05-data/data-model.md) |
| 开发与验收 | [实施计划](docs/plans/2026-09-20-mock-first-platform-integration.md)、[todo](docs/07-development/todo.md)、[验收](docs/07-development/acceptance.md) |
| 合成联调样例 | [examples/](examples/README.md) |
| 已知限制 | [known-limitations](docs/integration/known-limitations.md) |
| 项目交接 | [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) |
