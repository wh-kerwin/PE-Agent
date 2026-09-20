# 合成联调样例

这些数据完全虚构，用于验证契约和 UI，不代表真实 fab、Jev 实际响应或经工程确认的根因。

- `case-yield-drop.json`：宿主 Case 快照。
- `jev-assessment.json`：符合 TypeSafe response 形状的模拟判断，明确标记 synthetic。
- `analysis-result.json`：完整结构化报告。
- `sse-events.jsonl`：可恢复事件序列。

运行 `python scripts/validate_contracts.py` 校验报告 Schema、引用关系、事件顺序和文档链接。
