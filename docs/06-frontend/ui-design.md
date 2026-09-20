# Dashboard 嵌入式 UI 设计

入口在现有 Case Table 操作列。按钮状态：AI 分析、分析中（spinner）、查看分析、重新分析；无权限/不支持时禁用并用 tooltip 给出原因。按钮不能使列宽或行高变化。

桌面端用右侧 Drawer（建议宽 720–880px，受视口约束），保留列表上下文；窄屏用全屏面板。Header 固定显示 Case ID、类型、严重度、Case 数据版本和任务状态。主体顺序：进度/缺口 → Summary & Impact → Hypotheses → Findings/Evidence → Timeline → Similar Cases → Recommendations → Review。

Evidence 默认摘要，展开显示来源、事件时间、读取时间、单位、数据质量和「查看原始数据」。Hypothesis 同时显示支持、反证、缺失证据与“AI 假设”标签。Jev 的数值只在确有工程价值时以“模型判断信号”展示，不用虚假精确的圆环分数包装成根因概率。

运行中展示服务端真实事件；SSE 断开显示“正在恢复连接”，不把断线误报成分析失败。PARTIAL_RESULT 保留可用内容并在顶部列缺失源。刷新先加载快照，骨架保持稳定尺寸。报告文本纯文本渲染，来源链接只使用 API 返回的受控路由。

Feedback 分两步：可选 Helpful；必选工程结论（确认、修正、证据不足）。Case Book 保存按钮仅在复核后显示，并有独立成功/失败状态。UI 不提供 Hold Lot、停机或修改 Recipe 操作。

可访问性：图标按钮含可访问名称和 tooltip；状态不用颜色单独表达；键盘焦点进入 Drawer、Esc 关闭前确认未提交表单；进度更新使用非打断式 live region；表格与抽屉支持 200% 缩放。
