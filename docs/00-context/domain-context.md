# 领域上下文

产品是现有 Dashboard 的 Case 分析功能，调查单位是 Case，执行单位是 AnalysisTask。同一 Case 可有多次任务；Case 状态由宿主平台拥有，任务状态由 AI Gateway 拥有。

| 术语 | 含义与边界 |
|---|---|
| Case | 异常记录，含 ID、类型、症状、严重性、实体关联、发生时间与版本 |
| Lot / Wafer | 批次与晶圆；Wafer 必须携带 Lot 归属，不能只按槽位全局识别 |
| Tool / Chamber | 设备与腔体；不同腔体数据不可不加说明混合 |
| Recipe / Process Step | 配方版本与工艺步骤；对照必须匹配产品、步骤、时间与版本 |
| SPC | 统计过程控制；控制限需带适用规则和版本，不能用规格限替代 |
| FDC | 设备传感与故障检测；需采样单位、时间窗与采样质量 |
| Evidence | 由可信数据源产生的可追溯记录，包含 eventTime 和 retrievedAt |
| Hypothesis | 待工程验证的可能根因；不是已确认结论 |
| Case Book | 工程师复核后的历史经验，包含 AI 原稿和人工结论的独立版本 |

事实层级：Observed（实测事实）、Inferred（有证据的推断）、Hypothesis（根因假设）、Recommendation（建议）、Engineer Decision（人工结论）。历史案例和 SOP 不能冒充当前 Case 实测证据。

时间统一 ISO 8601 带偏移，存储 UTC，展示按平台时区。良率使用 0–100 的 percent，96 到 82 是下降 14 percentage points；相对下降为约 14.58%，二者不得混用。影响范围分别说明 confirmed 与 suspected，查询缺失不等于零影响。

V1 的 YIELD_DROP 以同条件基线为对照。没有匹配对照时明确限制，不宣称排除了设备、配方或材料因素。请求中的 tenantId、用户角色或列表快照不能替代服务端权限判定。
