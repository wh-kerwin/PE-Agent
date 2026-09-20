# Agent Evaluation

## Golden Dataset

每条历史 Case 包含：
- Case Input
- Expected Relevant Data
- Confirmed Root Cause
- Evidence
- Final Resolution
- Engineer Feedback

## V1

重点：
- Evidence Accuracy
- Hallucination
- RCA Agreement
- Recommendation Quality

## V2

增加：
- Plan Quality
- Tool Selection
- Similar Case Precision
- Knowledge Grounding
- Cross-Correlation Accuracy

## V3

增加：
- Action Safety
- Approval Correctness
- Execution Success
- Verification Accuracy
- False Action Rate

## Evaluation Modes

### Offline
历史 Case 回放。

### Shadow
真实环境只读运行，不影响生产。

### Pilot
受控用户试用。

### Production
按权限正式运行。
