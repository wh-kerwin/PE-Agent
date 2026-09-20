# Tool Registry

V1 注册表来源是 [tool-registry.json](../../agent/tools/tool-registry.json)。模型看不到 URL、认证或任意查询能力，只能从公开名称与输入定义中选择；Runtime 解析成固定适配器。

| 工具 | 用途 | 关键约束 |
|---|---|---|
| get_case_context | Case、版本与关联实体 | 必须先调用；资源权限检查 |
| get_lot_yield | Lot/Wafer 良率和基线 | 产品/步骤/Recipe 对照条件 |
| get_tool_events | 设备、腔体、报警、PM 时间线 | 明确事件窗与时区 |
| get_recipe_snapshot | 运行时 Recipe 版本与受控 diff | 不返回可写接口 |
| get_spc_evidence | 参数、控制限、规则违反 | 单位和 limit version 必需 |
| get_fdc_evidence | 参数趋势、漂移、采样质量 | 禁止用缺测点填零 |
| search_similar_cases | 权限内历史 Case | 只返回已解决且可见记录 |

所有工具返回 `data`, `source`, `eventTime/retrievedAt`, `quality`, `rawRef`。默认超时 8 秒；只对明确幂等读取错误做一次带 jitter 重试，且不突破总预算。原数据链接由服务端根据 sourceId 生成。
