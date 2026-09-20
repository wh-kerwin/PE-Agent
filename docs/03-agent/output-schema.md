# Analysis Report 契约

权威机器契约是 [analysis-report.schema.json](../../agent/schemas/analysis-report.schema.json)。报告版本 `1.0.0`，与 Task Envelope 和 Engineer Review 分开。

报告固定包含 summary、impact、timeline、findings、evidence、correlations、hypotheses、similarCases、recommendations、uncertainties。即使为空也显式给数组；部分报告需有至少一项 uncertainty 说明缺口。

关键引用规则：finding/correlation/hypothesis/recommendation 的 evidenceIds 必须在本报告 evidence 中存在；hypothesis 必须同时列 supporting、contradicting 和 missing。`confidenceLevel` 为 LOW/MEDIUM/HIGH 的证据一致性标签，`modelAssessment` 可记录 Jev primitive、答案、分布、confidence/noul 和实际版本，但不暴露内部推理。

前端不直接渲染模型 HTML/Markdown。文本作为纯文本处理，原数据跳转只使用后端构造的 `rawRef`。
