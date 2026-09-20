# 前端状态与恢复

推荐一个按 caseId 索引的 analysis store。实体：`tasksById`、`latestTaskByCase`、`reportsByTaskVersion`、`reviewsByTask`；连接状态单独存储。

动作：openCaseAnalysis、createOrResume、loadTaskSnapshot、connectStream、applyEvent、reconnectFrom、submitReview、archiveCaseBook、retryAsNewTask、cancelTask、closeDrawer。

事件 reducer 只接受比 `lastSequence` 大的同 task 事件。`report_generated` 触发 GET，不从事件拼完整报告。浏览器仅在 sessionStorage 保存非敏感的 taskId、caseId、lastEventId；权限错误立即清理可见缓存。切换 Case 时取消旧订阅但不取消后台任务。

避免竞态：每次请求带 active task guard；旧 Case 的迟到响应不覆盖当前 Drawer；retry 返回新 taskId 后保持旧报告可查看。列表摘要由宿主刷新，不由 Drawer 私自改 Case 状态。
