# Frontend UI Design

## V1: Case Analysis Drawer

入口：
Case List → AI Analysis。

### Header
Case ID / Type / Severity / Status / Task Status

### Progress
实时展示调查步骤。

### Report
Summary / Impact / Timeline / Findings / Evidence / RCA / Recommendations。

## V2: Investigation Workspace

从 Drawer 升级为大尺寸 Workspace。

布局：

左侧：
- Case Context
- Investigation Plan

中间：
- Timeline
- Correlation Graph
- Findings

右侧：
- Evidence
- Root Cause
- Knowledge
- Recommendations

底部：
- Follow-up Input

## V3: Action Center

新增：
- Action Cards
- Risk Badge
- Approval
- Execution
- Monitoring
- Verification

## UI 原则

- AI finding 与 Engineer decision 明确区分
- Evidence 可点击回原系统
- 重要结论不隐藏在长文本
- 长任务必须展示进度
- SSE 断开后可以恢复
