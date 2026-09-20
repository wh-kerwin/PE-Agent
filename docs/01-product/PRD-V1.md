# PE Case Analysis Agent — PRD V1.1

日期：2026-09-20。状态：待工程实施的需求基线。依据原 V1 PRD 与用户对嵌入式功能的补充说明重整。

## 1. 产品定义与价值

在现有 PE Duty / Engineer Platform Dashboard 的 Case List / Table 中，每一条支持的 Case 提供「AI 分析」按钮。点击即围绕该 Case 启动制造异常调查，在当前页面的 Drawer 展示相关数据、证据、根因假设和处置建议，工程师做最终判断。

调查对象是 Case；Lot、Wafer、Tool / Chamber、Recipe、Process Step、SPC / FDC 和历史 Case 提供上下文。用户不必先编写问题，也不必复制整行数据给模型。平台继续负责 Case 列表、筛选、登录、权限、生产操作与 Case Book。

业务目标是缩短 Case Investigation Time。原 PRD 中 30 分钟降至 10 分钟是试点目标示例，需采集同类 Case 基线后验证，不是已实现收益。

## 2. 用户与场景

| 用户 | 主要问题 | 优先呈现 |
|---|---|---|
| PE Duty | 是否紧急、影响哪些对象、下一步做什么 | 摘要、影响、立即建议 |
| Process Engineer | 工艺/设备/配方变化是否有关 | 时间线、SPC/FDC、假设与反证 |
| Yield Engineer / PIE | Wafer 分布、良率损失与跨实体关系 | 影响范围、对照数据、相似案例 |

V1 场景：Yield Drop。示例 LOT001 良率由 96% 降至 82%，绝对下降 **14 个百分点**。Agent 查询该 Lot 的工艺时间窗与设备数据，若查到压力超限，只能形成关联和待验证假设；不能仅凭时间先后确认根因。

## 3. 产品边界

| V1 必须交付 | 后续演进 / V1 不包含 |
|---|---|
| Case 行入口、Drawer、进度和恢复 | 独立运营 Dashboard、通用聊天首页 |
| Yield Drop、Lot/Wafer/Tool/Recipe/SPC/FDC 读取 | 全类型 Case 一次覆盖 |
| 历史案例检索、基础同条件对照 | 高级知识图谱、自动训练、多 Agent |
| 证据、时间线、相关性、根因假设、建议 | 自动确认根因、自动关闭 Case |
| 工程师反馈、复核后显式归档 Case Book | 自动 Hold/Release Lot、停机、修改 Recipe、MES 写操作 |

反馈与归档属于受权限控制的应用数据写入；制造工具本身只读。SOP 检索接口可预留，全面知识库治理放 V2。

## 4. 主交互与功能需求

| 编号 | 需求 | 可观察行为 |
|---|---|---|
| FR-01 | Case 行 AI 分析入口 | 未分析显示「AI 分析」；运行中「分析中」；有报告「查看分析」；无权限禁用并解释 |
| FR-02 | Case 绑定与可信上下文 | 前端发 caseId、可选 caseVersion；后端按登录身份重新查询，记录快照版本 |
| FR-03 | 异步任务 | 创建后立即返回 taskId；刷新、关闭抽屉不取消后台任务 |
| FR-04 | 实时调查进度 | 展示读取 Case、查询数据、分析、生成报告等真实阶段；不展示内部思维链 |
| FR-05 | 制造数据调查 | 受限计划调用白名单工具；有来源与时间；工具失败不伪装成正常 |
| FR-06 | 结构化报告 | 展示本节下方列出的固定区域；无数据明确标出缺口 |
| FR-07 | 异常恢复 | 重连续传、快照恢复、部分结果、显式重试/取消、过期结果提醒 |
| FR-08 | Engineer Review | Helpful 评价与根因复核分开；可接受、修正或标为待调查 |
| FR-09 | Case Book | 工程师显式保存复核结果；显示成功/失败；幂等重试；不执行生产动作 |
| FR-10 | 审计与隔离 | 每次请求/重连/工具查询/归档均检查资源权限，可追踪任务版本和来源 |

报告区域：Case Summary、Impact、Timeline、Key Findings、Data Evidence、Correlation Analysis、Potential Root Causes、Historical Similar Cases、Recommended Actions、Uncertainties、Engineer Feedback。前十项来自报告；最后一项是独立的人工记录。

每个关键发现/关联/假设/建议绑定 evidenceIds；来源可由平台路由跳转到原系统。假设标注支持证据、反证、待验证项与定性置信等级。置信等级表达证据一致性，不解释成概率。建议按 Immediate / Investigation / Follow-up 分类，注明由工程师在原平台执行。

## 5. 任务与人工复核状态

执行主路径：CREATED → CONTEXT_LOADING → INVESTIGATING → ANALYZING → GENERATING_REPORT → COMPLETED。
异常终态：PARTIAL_RESULT、FAILED、TIMEOUT、CANCELLED。COMPLETED 表示报告生成完毕，不表示根因已确认或 Case 已关闭。

reviewStatus 独立取 NOT_REVIEWED / CONFIRMED / CORRECTED / INCONCLUSIVE。原稿 WAITING_ENGINEER_REVIEW 合并为「执行完成 + NOT_REVIEWED」，避免人工迟迟未复核使计算任务永远运行。Case Book 使用独立归档记录，不复用执行状态。

非关键数据源缺失且仍有可用证据：PARTIAL_RESULT + 报告 + 明确缺口。Case 无法读取或无任何可信证据：FAILED，不构造诊断报告。总预算耗尽但已有可验证报告时可返回 PARTIAL_RESULT，否则 TIMEOUT。

## 6. 接口与集成

保留原 API 前缀 `/api/ai/case-analysis`；创建、查询、SSE、反馈、重试、取消和归档详见 [业务 API](../04-api/api-spec.md)。同一授权范围内 Case/版本的运行任务去重。重新分析生成新 taskId，并保留原报告。

推荐现有页面内组件 + 同源 BFF/AI Gateway + 后台 Worker。平台登录身份不进入模型提示词作为授权依据。列表显示来自宿主系统，Agent 不重建 Case 管理系统。Vue3 + Arco 是原 PRD 的推荐实现；API 契约不依赖该框架。

## 7. 模型与 Agent

V1 单 Agent、受限动态规划、只读 Tool Registry、证据校验、结构化输出。模型负责理解、选择调查步骤和总结；运行时负责权限、调度、预算、Schema 校验、证据引用、持久化与审计。

TypeSafe Jev 是 System One 决策模型，接收 state 与 typed questions，返回 Choice / Score / Noul；它不负责直接生成完整长报告或调用制造工具。采用 [Jev 集成设计](../02-architecture/model-integration.md)：Runtime 取数并控制工作流，Jev 评估原子问题，代码校验引用并组装报告。自然语言解释可使用确定性模板，未来如引入生成式模型需独立评估。

## 8. 性能、质量与验收

| 指标 | 试点目标 | 口径 |
|---|---|---|
| Case 上下文 | p95 < 2s | Worker 开始加载至快照就绪 |
| 首次用户可见进度 | p95 < 3s | 点击至服务端真实进度事件；不是首个推理 token |
| 普通/复杂分析 | p95 < 30s / < 60s | 接受任务至终态，包含排队；复杂标签在分析前确定 |
| 单次工具调用 | < 10s | 默认截止时间 8s；重试仍受任务总预算约束 |
| 完整分析成功率 | > 95% | COMPLETED / 已接受非用户取消任务，部分结果单列 |
| 引用完整性 | 100% | 报告中的所有引用可解析到当前任务证据 |
| 不支持的事实断言 | 发布评审样本为 0 | 专家复核，不仅检查 JSON 格式 |

以上是目标，未有运行测量。详细异常用例和验收映射见 [验收标准](../07-development/acceptance.md)。

## 9. V1 交付与未决项

交付路径：合成样例闭环 → 真实只读数据联调 → 已确认历史 Case 离线评估 → 受控试点。需平台方提供 Case API/版本字段、身份与资源权限、各制造系统接口、Case Book 写入协议、模型正式资料和部署限制。未决项记录在 [TODO](../07-development/todo.md)，不能把 mock 通过视为生产接入完成。
