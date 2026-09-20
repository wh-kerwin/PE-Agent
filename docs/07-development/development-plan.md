# V1 实施计划

## 0. 真实契约发现

确认宿主 Case 模型/版本、IAM 委托、Lot/Wafer/Tool/Recipe/SPC/FDC/Case Book API、数据时区/单位、TypeSafe 数据出域与账号。产出脱敏真实样例、字段映射和权限矩阵。

## 1. Vertical Slice

Case 行按钮 → 创建持久任务 → mock 只读工具 → SSE 恢复 → Schema 报告 → Engineer Review。先证明嵌入与状态边界，再扩充调查。

## 2. Yield Drop 调查

实现 Tool Registry 和适配器、证据标准化、固定工作流、对照逻辑、历史 Case、部分结果。工具和 Evidence 使用契约/集成测试。

## 3. Jev 判断层

实现 System One 客户端与问题模板，固定 `jev-1.13.0` 做评估基线；记录 resolved model。用黄金 Case 校准阈值，验证 CJK；超时/429/529 进入降级路径。Jev 不阻塞确定性报告骨架。

## 4. 报告与试点

语义验证、来源深链、Case Book 幂等归档、审计/指标、离线回放、shadow 和受控 PE 试点。通过发布门槛后再讨论 V2。

每阶段有可演示闭环和退出标准；依赖真实企业 API 的任务不可用 mock 标记完成。frontend/backend 的具体技术实现需基于其现有项目约束另行拆分计划。
