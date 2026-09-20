# 数据流与一致性

1. Browser 发送 caseId 和可选 caseVersion，Gateway 从会话取得用户/租户/资源范围。
2. Case Adapter 校验访问并读取当前版本。若客户端版本过旧返回 409，不默默分析不同版本。
3. 事务创建 task、幂等记录及待调度 outbox。Worker 获取租约，持久化可信上下文和 contextHash。
4. 工具请求仅携带该任务允许的实体和时间窗；结果经 Evidence Engine 标准化，记录输入哈希与来源引用。
5. Agent 生成带引用的候选报告。Schema 与语义校验通过后，同一事务保存 report、任务终态及 report_generated / analysis_completed 事件。
6. SSE 发布已提交事件；断线回放按序号进行。客户端最终通过 GET 获得权威快照。
7. 工程师提交独立人工记录；归档操作写入 Case Book 适配器，保存外部 ID 和幂等结果。

任务终态采用 compare-and-set，取消与完成竞态只允许一个终态胜出。终态后迟到工具结果可保留审计但不得改写报告。反馈可追加审计版本，不覆盖 AI 原稿。

Case 更新不会原地变更已生成报告；报告标记原 caseVersion 与数据时间。重新分析建立新任务。重连、刷新和重复点击不能创建新的推理循环。
