# Frontend Component Design

```text
CaseDashboard
├── CaseTable
│   └── AIAnalysisButton
└── CaseAnalysisWorkspace
    ├── AnalysisHeader
    ├── CaseContextPanel
    ├── InvestigationPlan
    ├── ProgressTimeline
    ├── EventTimeline
    ├── CorrelationGraph
    ├── FindingsPanel
    ├── EvidencePanel
    ├── SimilarCasesPanel
    ├── KnowledgePanel
    ├── RootCausePanel
    ├── RecommendationPanel
    ├── ActionCenter
    ├── VerificationPanel
    └── EngineerFeedback
```

建议基于 Vue3 + Arco Design Vue。

图谱可独立封装，不让 Agent 逻辑耦合 UI。
