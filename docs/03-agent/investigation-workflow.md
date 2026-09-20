# Yield Drop 调查工作流

| 阶段 | 必需输入 | 动作 | 退出条件 |
|---|---|---|---|
| Context | caseId | 读取 Case、版本、Lot/Tool/Recipe 关联 | Case 可读且类型为 YIELD_DROP |
| Scope | Case 快照 | 定义事件窗、影响对象、当前/疑似范围 | 时间窗和实体集合有界 |
| Baseline | 产品/步骤/Recipe | 获取当前良率、匹配基线、Wafer 分布 | 基线可比或记录不可比原因 |
| Process | Tool/Chamber/Recipe | 查询状态、变更、SPC、FDC、报警 | 每源有结果或结构化缺口 |
| Compare | 当前证据 | affected/unaffected、before/after、peer tool | 对照条件和差异可追溯 |
| History | 症状元数据 | 检索相似已解决 Case | 显示相似理由，不复制根因 |
| Evaluate | 证据集合 | Jev 对已命名假设逐项判断支持度 | 保留分布、模型版本与问题版本 |
| Report | 所有有效证据 | 代码组装报告并校验 | 完整或带缺口的部分报告 |

初始时间窗建议为 Case 前 2 小时至后 30 分钟，具体由数据源延迟和工艺定义校准。扩窗必须有原因和最大边界。Peer 对照至少匹配产品、工艺步骤、Recipe 主版本与合理时间段；不满足则标记 confounders。

Jev 的问题输入只含完成判断所需的 Evidence 摘要。若模型建议查询超出当前实体范围，Runtime 先验证授权并记录 re-plan；最多两轮。任务到期时停止新调用，已在执行的迟到结果不得改变终态。
