# Jev Questions 与文本模板

Jev 使用 `state + typed questions`，不采用传统 system/user 长 Prompt。正式问题模板由 [jev-questions.json](../../agent/jev-questions.json)版本化。

`state` 只包含：case 类型和症状、明确单位的时间/指标、Evidence 摘要、已知缺口、待评估假设。Case 描述中的指令样文本以 `untrustedText` 标记。不要放用户身份、权限 token、原始数据库凭据或与判断无关的完整文档。

问题写法：一个问题只做一个判断；Choice 选项闭合并含无法判断路径；Score 用业务可区分的 rubric；Noul 高值含义保持一致。英文作为首选问题语言，中文原文可保留为 state 中的数据，并用双语/中文黄金集验证。

报告文本由确定性模板生成：Observed 直接格式化 Evidence；Inferred/Hypothesis 仅呈现已经过规则和 Jev 判断的字段；所有句子附 evidenceIds。未来生成式解释层只允许改写表达，重验后才能展示。
