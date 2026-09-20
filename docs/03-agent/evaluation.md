# 评估方案

## 数据集

每条黄金 Case 包含固定数据快照、允许工具结果、专家相关证据、已确认根因或 INCONCLUSIVE、合理建议和不可访问字段标记。按 Tool、Recipe、产品、时间分层，训练/阈值校准/最终测试分离，避免同一事件泄漏。

## 指标

| 维度 | 指标 |
|---|---|
| Grounding | unsupported claim rate、citation precision/recall、数值一致性 |
| Investigation | 必需工具召回、无关工具率、范围越界率、预算/时延 |
| Hypothesis | top-k expert agreement、反证覆盖、INCONCLUSIVE 召回 |
| Jev | Choice/Score/Noul 按问题的准确率、校准误差、置信分桶、版本漂移 |
| Safety | 跨租户读取、prompt injection、生产写调用、敏感字段出域均为零 |
| Product | 调查耗时、复核耗时、修正率、Case Book 复用；Helpful 单独统计 |

先对确定性规则与 Schema 做自动测试，再离线回放，最后 shadow mode。Jev 问题或模型版本更新必须重跑冻结测试集；阈值在校准集上确定，在测试集上只评估一次。中文/CJK Case 单独报告质量。

试点发布门槛由 PE/工艺/安全/平台共同批准。合成样例只能验证契约，不能用于声称 RCA 准确率。
