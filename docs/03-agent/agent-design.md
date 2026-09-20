# Agent 设计

V1 是一个有界状态机，不是开放式自主聊天 Agent。Runtime 拥有控制流，Jev 负责若干原子判断。

## 不变量

1. 只能分析请求用户有权读取的 Case 和关联实体。
2. 工具调用必须存在于注册表并通过参数、范围、预算校验。
3. Observed 数据只来自工具结果；模型输出不能创建事实。
4. 每个 Finding、Correlation、Hypothesis 和 Recommendation 引用已有 evidenceId。
5. Hypothesis 永远不写成 confirmed root cause；Engineer Review 独立存储。
6. COMPLETED 只表示报告生成完成。
7. V1 无生产写工具。

## 运行阶段

`load_context → establish_scope → collect_baseline → collect_process_data → build_timeline → evaluate_hypotheses → compose_report → validate_report`。

固定阶段确保核心证据不会被跳过；Jev Choice 可在允许分支间排序下一查询，Noul/Score 可评估指定假设。任何模型选择都经代码映射为预定义 ToolSpec。缺乏 Jev 结果时仍可走确定性流程，报告标记判断缺口。

输出校验分两层：JSON Schema 检查形状；语义校验检查引用存在、实体属于上下文、数值可从证据复算、时间排序、枚举和终态一致。失败不向用户发布伪完整报告。
