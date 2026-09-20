# V1 验收标准

| ID | Given / When / Then |
|---|---|
| AC-01 | 有权限的 Yield Drop Case 点击 AI 分析，3 秒目标内出现真实任务进度且列表上下文保留 |
| AC-02 | 重复点击或刷新同一运行任务，不创建第二个任务并恢复已落库进度 |
| AC-03 | 客户端 caseVersion 过期时返回 409，不分析另一个快照 |
| AC-04 | 每个 Finding/Hypothesis/Recommendation 的证据引用可解析并打开授权来源 |
| AC-05 | 缺失 FDC 等非关键源时返回 PARTIAL_RESULT，缺口明确，已验证内容仍可读 |
| AC-06 | 无可信证据时不生成根因结论，显示 INSUFFICIENT_EVIDENCE |
| AC-07 | Jev 429/529/超时按预算退避并降级；UI 不将模型不可用显示为已确认结论 |
| AC-08 | Jev Choice/Score/Noul 原始分布、实际版本与问题版本可审计，confidence 不呈现为根因概率 |
| AC-09 | 越权 taskId、重连、rawRef、关联 Tool/Lot 均拒绝，跨租户测试无数据泄漏 |
| AC-10 | Case 描述中的提示注入不能改变工具白名单、权限或输出契约 |
| AC-11 | 工程师可独立提交 Helpful 与复核状态；修正不覆盖 AI 原报告 |
| AC-12 | Case Book 归档只有复核后允许；重复请求幂等，失败可重试 |
| AC-13 | 取消/完成竞态只产生一个终态；迟到结果不改写报告 |
| AC-14 | 键盘、屏幕阅读器状态提示、200% 缩放和移动全屏面板通过检查 |

性能目标以 PRD 口径做 p95 测量。发布还要求 Schema/链接校验、单元与集成测试、历史 Case 离线评估、shadow 观察和 PE/安全签字。合成样例通过只证明契约成立。
