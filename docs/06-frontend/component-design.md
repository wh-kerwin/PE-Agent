# 前端组件边界

```text
CaseTable
└── CaseAnalysisAction

CaseAnalysisDrawer
├── AnalysisHeader
├── AnalysisProgress
├── DataGapAlert
├── SummaryImpact
├── HypothesisList
│   └── EvidenceReferenceList
├── FindingList / Timeline / SimilarCaseList
├── RecommendationList
└── EngineerReviewForm / CaseBookArchiveStatus
```

宿主 CaseTable 只传 `caseId`, `caseVersion`, `analysisSummary` 和打开事件；Drawer 自行通过 API 恢复任务，避免表格行持有完整报告。原系统跳转由统一 `openSource(rawRef)` 处理并再次授权。

组件按 TaskEnvelope、AnalysisReport、EngineerReview 三个类型分层，禁止把 SSE payload 直接作为最终页面状态。相关图谱不在 V1 首屏；已有 `correlations` 用列表表达，V2 再引入图可视化。
