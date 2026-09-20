# Evidence 模型

Evidence 是可验证观测，不是模型意见。分类：CASE、YIELD、WAFER、TOOL_EVENT、RECIPE、SPC、FDC、HISTORICAL_CASE。

状态：VERIFIED（来源和字段校验通过）、PARTIAL（缺字段/缺时间段）、CONFLICTING（与另一来源不一致）、UNAVAILABLE（只记录缺口，不提供观察值）。检索成功不等于业务正确；quality 需保留数据延迟、缺测和采样异常。

关系类型：OCCURRED_BEFORE、SAME_CONTEXT、DIFFERS_FROM、CORRELATES_WITH、SUPPORTS、CONTRADICTS。时间先后和相关性都不能自动升级为 CAUSES。一个 Evidence 可以支持多个 Hypothesis；角色由关系记录，不写死在 Evidence 本身。

语义校验：所有报告引用必须存在；来源 ID、时间和单位不可由模型改写；派生数值保存公式和输入 IDs；相似历史 Case 只能作辅助证据；SOP 属知识参考，不属于当前 Case 实测证据。
