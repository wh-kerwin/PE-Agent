# PE Case Analysis Agent

嵌入 PE Duty / Engineer Platform Dashboard 的 **AI Case 分析功能**。
工程师在现有 Case List / Table 行末点击「AI 分析」，打开分析抽屉，查看调查进度、证据、根因假设与建议，确认或修正后归档 Case Book。

## 当前状态

2026-09-20：产品与工程设计基线 V1.1。仓库包含需求、接口契约、Agent 配置和合成样例，**尚未实现运行服务或平台集成**。`frontend/`、`backend/` 保留原状。`agent/` 是声明式设计资产，尚无执行器。示例不是生产调查结果。

## 一次分析

```mermaid
sequenceDiagram
    actor E as Engineer
    participant UI as Dashboard / Drawer
    participant API as AI Gateway
    participant A as Agent Runtime
    participant D as Manufacturing Tools
    E->>UI: 点击 Case 行 AI 分析
    UI->>API: POST caseId + caseVersion
    API-->>UI: 202 taskId
    API->>A: 持久化任务后调度
    A->>D: 按用户权限读取数据
    D-->>A: 数据 + 来源 + 时间
    API-->>UI: SSE 进度 / 报告就绪
    UI->>API: GET 任务与完整报告
    E->>UI: 复核 / 修正 / 保存 Case Book
```

## 阅读入口

| 内容 | 入口 |
|---|---|
| V1 产品基线 | [PRD-V1](docs/01-product/PRD-V1.md) |
| 用户交互 | [用户旅程](docs/01-product/user-journey.md)、[Drawer 设计](docs/06-frontend/ui-design.md) |
| 嵌入与部署 | [系统架构](docs/02-architecture/system-architecture.md) |
| Jev 接入边界 | [模型适配](docs/02-architecture/model-integration.md) |
| 调查与模型约束 | [Agent 设计](docs/03-agent/agent-design.md)、[Agent 资产](agent/README.md) |
| API / SSE | [业务 API](docs/04-api/api-spec.md)、[事件协议](docs/04-api/sse-events.md) |
| 数据契约 | [报告 Schema](agent/schemas/analysis-report.schema.json)、[数据模型](docs/05-data/data-model.md) |
| 开发与验收 | [开发计划](docs/07-development/development-plan.md)、[验收](docs/07-development/acceptance.md) |
| 合成联调样例 | [示例说明](examples/README.md) |
| 重整说明 | [变更记录](docs/07-development/regeneration-notes.md) |

## 范围

V1：Yield Drop、单 Agent、只读工具、可恢复 SSE、结构化报告、工程师复核和 Case Book 归档。
V2：[多类型 Case 与交互调查](docs/01-product/PRD-V2.md)。V3：[审批后受控动作](docs/01-product/PRD-V3.md)。后两者是路线图。

TypeSafe Jev 已按官方文档纳入设计：它用于 Choice / Score / Noul 原子判断，由代码控制调查与组装报告。当前仓库仍未配置 API Key 或实现适配器，不声称已经接入运行环境。

## 本地资料校验

Python 3.10+，在已有 `jsonschema` 的环境运行：

```sh
python scripts/validate_contracts.py
```

缺少依赖时执行 `python -m pip install -r scripts/requirements.txt`。校验覆盖 Schema、样例、引用关系、SSE 和文档链接；不代表服务端或 UI 已通过功能测试。
