# PE Case Analysis Agent

## 半导体 PE Duty / Engineer 平台智能 Case 分析 Agent

**文档版本：** V1.0
**文档状态：** 产品方案 / 技术评审版
**适用平台：** PE Duty Platform / Engineer Platform
**目标用户：** PE Duty、Process Engineer、Yield Engineer、PIE 等工程人员
**核心能力：** 基于 Case 上下文和制造数据，对异常 Case 进行自动调查、关联分析、根因推理和处置建议

---

# 1. 产品概述

## 1.1 背景

在半导体制造环境中，PE Duty 或 Engineer 每天会面对大量 Case，例如：

* Lot Hold
* Yield Drop
* Tool Down
* Tool Status 异常
* SPC Out of Control
* FDC Alarm
* Recipe 异常
* Wafer 参数异常
* Process Parameter Drift
* Equipment 异常
* Lot-to-Lot Variation
* Wafer-to-Wafer Variation
* Quality / Defect 异常

当前 Case 处理通常依赖工程师人工进行：

```text
发现 Case
  ↓
查看 Case 基本信息
  ↓
查询 Lot
  ↓
查询 Wafer
  ↓
查询 Tool
  ↓
查询 Recipe
  ↓
查看 SPC
  ↓
查看 FDC
  ↓
查看历史 Case
  ↓
查询相似 Lot / Tool
  ↓
人工判断可能原因
  ↓
给出处理方案
```

整个过程涉及多个系统、多个数据源以及工程师自身经验。

因此，本产品希望在现有 PE Duty / Engineer 平台中引入 **Case Analysis Agent**。

工程师无需主动切换多个系统，而是在 Case 列表中直接点击：

**AI Analysis**

Agent 自动围绕 Case 展开调查，并形成结构化分析结果。

---

# 2. 产品目标

## 2.1 核心目标

建立一个面向半导体制造 Case 的专业 Agent：

> **让工程师从“自己找数据、自己分析”转变为“Agent 帮助调查，工程师做最终判断”。**

Agent 不只是回答问题，而是能够：

1. 理解 Case
2. 自动获取相关上下文
3. 调用制造数据接口
4. 检索历史 Case
5. 分析 Lot / Wafer / Tool / Recipe / Process 数据
6. 进行跨数据源关联
7. 推导可能原因
8. 给出证据
9. 提供下一步建议
10. 保留完整分析过程和数据来源

---

# 3. 产品定位

本产品不是普通 Chatbot。

### 普通 Chatbot

```text
Engineer
   ↓
输入问题
   ↓
LLM
   ↓
回答
```

### PE Case Agent

```text
Case
 ↓
Case Context
 ↓
Agent
 ↓
Plan Investigation
 ↓
调用制造数据 Tools
 ↓
多轮数据分析
 ↓
Evidence
 ↓
Root Cause Hypothesis
 ↓
Impact Assessment
 ↓
Recommended Actions
 ↓
Engineer Review
```

因此产品定位为：

> **Domain-specific Manufacturing Investigation Agent**

即：

**面向半导体制造异常调查的领域 Agent。**

---

# 4. 核心用户

## 4.1 PE Duty

主要关注：

* 当前异常是什么
* 是否需要立即处理
* 影响哪些 Lot
* 影响哪些 Tool
* 是否存在类似历史 Case
* 当前应该做什么

## 4.2 Process Engineer

主要关注：

* Process 参数变化
* SPC
* FDC
* Recipe
* Lot / Wafer 分布
* Tool correlation
* Root Cause

## 4.3 Yield Engineer / PIE

主要关注：

* Yield impact
* Wafer abnormality
* Defect correlation
* Historical trend
* Similar cases

---

# 5. 核心使用场景

## 场景一：Yield Drop Case

Case：

```text
Case ID: CASE-20260918-001
Lot: LOT123456
Process: Etch
Tool: ETCH-01
Yield: 82%
Baseline: 96%
```

工程师点击：

**AI Analysis**

Agent 自动：

```text
获取 Case
 ↓
获取 Lot 信息
 ↓
获取 Wafer Yield
 ↓
获取 Tool 状态
 ↓
获取 Recipe
 ↓
获取 SPC
 ↓
获取 FDC
 ↓
查询历史相似 Case
 ↓
分析关联关系
```

最终输出：

```text
Case Summary

Yield 从 96% 降至 82%。

主要异常集中在：
- Wafer 03~18
- Tool ETCH-01
- Recipe RCP-102

Evidence

1. ETCH-01 在该 Lot 前 2 个 Lot 出现 Chamber Pressure Drift
2. SPC 参数 Pressure 在 14:32 超过 3σ
3. 相同 Tool + Recipe 历史上出现过类似 Yield Drop
4. 其他 Tool 上相同 Recipe 未出现明显异常

Root Cause Hypothesis

高概率与 ETCH-01 Chamber Pressure Drift 相关。

Recommended Action

1. 检查 Chamber Pressure Sensor
2. 对 ETCH-01 执行 PM / Calibration Check
3. 暂停继续使用该 Tool 处理关键 Lot
4. 对受影响 Lot 进行 Review
```

---

# 6. 产品核心交互

## 6.1 Dashboard Case List

现有 Dashboard：

```text
┌───────────────────────────────────────────────────────┐
│ Case Dashboard                                        │
├───────────────────────────────────────────────────────┤
│ Filter: Tool / Lot / Process / Status / Time           │
├───────────────────────────────────────────────────────┤
│ Case ID │ Type │ Lot │ Tool │ Severity │ Status │ AI  │
│─────────┼──────┼─────┼──────┼──────────┼────────┼─────│
│ 001     │ Yield│ L001│ T001 │ High     │ Open   │ 🤖  │
│ 002     │ SPC  │ L002│ T002 │ Medium   │ Open   │ 🤖  │
│ 003     │ Tool │ L003│ T003 │ High     │ Hold   │ 🤖  │
└───────────────────────────────────────────────────────┘
```

新增：

**AI Analysis**

---

# 7. AI Analysis 主流程

```text
             Case List
                 │
                 ▼
          点击 AI Analysis
                 │
                 ▼
          创建 Analysis Task
                 │
                 ▼
        Case Context Builder
                 │
                 ▼
        ┌─────────────────┐
        │   PE Agent      │
        └─────────────────┘
                 │
                 ▼
          Investigation Plan
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
     Lot       Tool      Process
     Data      Data       Data
       │         │         │
       └─────────┼─────────┘
                 ▼
           Evidence Engine
                 │
                 ▼
          Correlation Analysis
                 │
                 ▼
          Root Cause Analysis
                 │
                 ▼
          Impact Assessment
                 │
                 ▼
       Recommended Actions
                 │
                 ▼
          Final AI Report
                 │
                 ▼
          Engineer Review
```

---

# 8. Agent 总体架构

## 8.1 系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    PE Duty / Engineer UI                    │
│                                                             │
│ Dashboard │ Case List │ Case Detail │ AI Analysis           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent Gateway                         │
│                                                             │
│ Authentication                                              │
│ Authorization                                               │
│ Request Management                                           │
│ Streaming / SSE                                              │
│ Analysis Task Management                                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  PE Case Analysis Agent                      │
│                                                             │
│ Context Understanding                                       │
│ Investigation Planner                                       │
│ Tool Selection                                              │
│ Reasoning                                                   │
│ Evidence Analysis                                           │
│ Root Cause Analysis                                         │
│ Recommendation Generation                                   │
└─────────────┬────────────────┬────────────────┬─────────────┘
              │                │                │
              ▼                ▼                ▼
       Manufacturing       Knowledge        Historical
           Tools             Base             Cases
              │                │                │
              ▼                ▼                ▼
        MES / SPC / FDC    SOP / Wiki      Case History
        Tool / Lot         Process Docs    Similar Cases
        Wafer / Recipe
```

---

# 9. Agent 内部架构

Agent 建议采用多模块架构，而不是单一 Prompt。

```text
PE Agent
│
├── Context Manager
│
├── Investigation Planner
│
├── Tool Router
│
├── Manufacturing Data Analyzer
│
├── Historical Case Retriever
│
├── Evidence Manager
│
├── Root Cause Analyzer
│
├── Impact Analyzer
│
├── Recommendation Engine
│
└── Response Generator
```

---

# 10. Context Manager

负责将 Case 转换为 Agent 可以理解的标准上下文。

输入：

```json
{
  "caseId": "CASE-001",
  "caseType": "YIELD_DROP",
  "lotId": "LOT001",
  "toolId": "ETCH01",
  "recipeId": "RCP001",
  "process": "ETCH",
  "severity": "HIGH",
  "createdTime": "2026-09-18 14:30:00"
}
```

Context Manager 自动扩展：

```text
Case
├── Lot
│   ├── Wafer
│   ├── Product
│   └── Route
│
├── Tool
│   ├── Chamber
│   ├── Status
│   ├── PM
│   └── Alarm
│
├── Recipe
│   ├── Version
│   └── Parameters
│
├── Process
│
├── SPC
│
├── FDC
│
└── Historical Cases
```

---

# 11. Investigation Planner

这是 Agent 与普通 Chatbot 最大的区别之一。

Agent 首先不直接回答，而是生成调查计划。

例如：

```text
Investigation Plan

Step 1
Analyze current Case

Step 2
Check affected Lot / Wafer

Step 3
Check Tool status and alarm history

Step 4
Check SPC trend

Step 5
Check FDC parameters

Step 6
Check Recipe changes

Step 7
Search similar historical cases

Step 8
Cross-correlate evidence

Step 9
Generate root cause hypotheses

Step 10
Generate recommended actions
```

Planner 可以根据中间结果动态增加调查步骤。

例如：

```text
发现 Pressure 异常
       ↓
Planner 判断需要进一步调查
       ↓
查询 Sensor Calibration
       ↓
查询 Chamber Maintenance
       ↓
查询历史 Pressure 异常
```

因此 Investigation Plan 是动态的。

---

# 12. Manufacturing Tools

Agent 不直接访问数据库。

通过 Tool 层访问企业数据。

建议建立统一 Tool Registry。

## 12.1 Lot Tools

```text
getLotInfo()
getLotHistory()
getLotRoute()
getLotYield()
getAffectedWafers()
```

## 12.2 Wafer Tools

```text
getWaferData()
getWaferMap()
getWaferMeasurements()
getWaferDefects()
```

## 12.3 Tool Tools

```text
getToolStatus()
getToolAlarm()
getToolHistory()
getToolPMHistory()
getToolChamberStatus()
```

## 12.4 Recipe Tools

```text
getRecipeInfo()
getRecipeVersion()
getRecipeChangeHistory()
compareRecipe()
```

## 12.5 SPC Tools

```text
getSPCChart()
getSPCViolation()
getSPCTrend()
getControlLimits()
```

## 12.6 FDC Tools

```text
getFDCData()
getFDCAlarm()
getParameterTrend()
detectParameterDrift()
```

## 12.7 Case Tools

```text
getCase()
searchCases()
getSimilarCases()
getCaseHistory()
```

---

# 13. Tool 调用原则

Agent 必须遵循：

### 原则一：最小权限

Agent 只能调用被授权的数据接口。

### 原则二：只读优先

V1 阶段：

```text
AI Agent
    ↓
Read Only
```

不允许直接执行：

* Hold Lot
* Release Lot
* Disable Tool
* Modify Recipe
* Change Process Parameter

所有高风险操作由工程师最终确认。

---

# 14. Knowledge Base

Agent 除了实时数据，还需要企业知识。

知识来源包括：

```text
SOP
Process Guide
Troubleshooting Guide
Equipment Manual
Recipe Guide
工程经验
Historical Case
FAQ
Yield Review
PM Documentation
```

建议：

```text
Knowledge Base
       ↓
Embedding / Retrieval
       ↓
Relevant Documents
       ↓
Agent
```

---

# 15. Historical Case Retrieval

这是 PE Agent 的关键能力。

例如当前：

```text
Tool = ETCH01
Recipe = RCP100
Process = ETCH
Issue = Yield Drop
```

Agent 查询历史 Case：

```text
Historical Cases

CASE-20260101
Tool: ETCH01
Issue: Yield Drop
Cause: Chamber Pressure

CASE-20260321
Tool: ETCH02
Issue: Yield Drop
Cause: Recipe Drift

CASE-20260710
Tool: ETCH01
Issue: Yield Drop
Cause: Sensor Calibration
```

Agent 不能简单地说：

> “历史 Case 表明一定是 Chamber Pressure。”

而应该输出：

```text
Historical Evidence

Found 3 similar cases.

2 cases involved ETCH01.
1 case involved the same Recipe.

The most common historical correlation
was Chamber Pressure abnormality.

This is supporting evidence, not confirmed root cause.
```

---

# 16. Evidence Engine

Agent 所有重要结论必须尽可能绑定 Evidence。

例如：

```text
Hypothesis:
Tool Chamber Pressure Drift

Evidence:
├── SPC Pressure > 3σ
├── FDC Pressure increased 8%
├── Alarm occurred 12 min before Case
├── Similar historical Case exists
└── Other tools using same Recipe were normal
```

最终形成：

```text
Conclusion
    ↓
Evidence
    ↓
Source
    ↓
Timestamp
```

---

# 17. Root Cause Analysis

V1 不建议直接使用：

> Root Cause = XXX

而使用：

### Root Cause Hypothesis

例如：

```text
Potential Root Cause #1
Chamber Pressure Drift

Confidence:
High

Supporting Evidence:
4

Contradicting Evidence:
1
```

```text
Potential Root Cause #2
Recipe Parameter Change

Confidence:
Medium

Supporting Evidence:
2

Contradicting Evidence:
2
```

这样可以降低 AI “一本正经胡说八道”的风险。

---

# 18. Root Cause 分析框架

可以采用：

```text
Case
 │
 ├── Time Correlation
 │
 ├── Tool Correlation
 │
 ├── Lot Correlation
 │
 ├── Wafer Correlation
 │
 ├── Recipe Correlation
 │
 ├── SPC Correlation
 │
 ├── FDC Correlation
 │
 └── Historical Correlation
```

最终形成：

```text
Correlation Graph

Case
 │
 ├── Lot001
 │    ├── Wafer03
 │    ├── Wafer04
 │    └── Wafer05
 │
 ├── Tool ETCH01
 │    └── Pressure abnormal
 │
 ├── Recipe RCP100
 │    └── Version changed
 │
 └── SPC
      └── Pressure > 3σ
```

---

# 19. AI Analysis UI

点击 AI Analysis 后，不建议直接弹一个普通 ChatGPT 对话框。

推荐设计成：

```text
┌──────────────────────────────────────────────────────┐
│ AI Case Analysis                              ● Live │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Case Summary                                         │
│ ─────────────────────────────────────────────────── │
│ Yield Drop detected on LOT001                        │
│ Tool: ETCH01     Recipe: RCP100                     │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Investigation                                    │ │
│ │                                                  │ │
│ │ ✓ Case context loaded                            │ │
│ │ ✓ Lot information analyzed                       │ │
│ │ ✓ Tool status checked                            │ │
│ │ ✓ SPC data analyzed                              │ │
│ │ ● FDC data analyzing...                          │ │
│ │ ○ Historical cases                               │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
└──────────────────────────────────────────────────────┘
```

采用流式输出。

---

# 20. 最终 Analysis Report

建议固定为结构化页面，而不是全部输出成长文本。

## 20.1 Case Summary

```text
Case Summary

Yield dropped from 96.2% to 82.4%.

Affected:
- Lot: LOT001
- Wafer: 03~18
- Tool: ETCH01
- Recipe: RCP100
```

---

## 20.2 Severity

```text
Impact

Affected Lots: 4
Affected Wafers: 72
Potential Yield Loss: 13.8%
Tool Impact: ETCH01
```

---

## 20.3 Key Findings

```text
Key Findings

1. Chamber Pressure abnormality occurred before Yield Drop
2. SPC exceeded control limit
3. FDC shows pressure drift
4. No corresponding abnormality on ETCH02
5. Similar historical cases were found
```

---

# 21. Root Cause

```text
Potential Root Causes

┌──────────────────────────────────────┐
│ 01 Chamber Pressure Drift            │
│ Confidence: High                     │
│                                      │
│ Supporting Evidence: 4               │
│ Contradicting Evidence: 1            │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ 02 Recipe Parameter Change           │
│ Confidence: Medium                   │
│                                      │
│ Supporting Evidence: 2               │
│ Contradicting Evidence: 2            │
└──────────────────────────────────────┘
```

注意：

Confidence 仅代表 Agent 对证据链一致性的判断，不代表真实概率。

---

# 22. Evidence

每个结论都可以展开：

```text
Evidence #1

Source:
SPC

Parameter:
Chamber Pressure

Observed:
+8.2%

Limit:
+5%

Time:
14:23:18

Related Lot:
LOT001
```

用户可以点击：

**View Original Data**

跳转原系统。

---

# 23. Recommended Actions

输出分成三类。

### Immediate

```text
建议立即：
- Hold affected Lot
- Check ETCH01 status
- Verify Chamber Pressure
```

### Investigation

```text
进一步调查：
- Check sensor calibration
- Review PM history
- Compare ETCH01 / ETCH02
```

### Follow-up

```text
后续：
- Monitor next 3 Lots
- Compare Yield trend
- Review similar historical cases
```

---

# 24. Engineer Feedback

Agent 输出后，工程师可以：

```text
👍 Helpful
👎 Not Helpful
```

并选择：

```text
Root Cause Correct
Root Cause Incorrect
Evidence Incorrect
Recommendation Useful
Recommendation Not Useful
```

同时允许：

```text
Engineer Comment
```

例如：

```text
Actual root cause:
Chamber Pressure Sensor Drift
```

这些数据用于后续 Agent Evaluation 和优化。

---

# 25. Agent 与人工协作

核心原则：

> **AI 调查，Engineer 决策。**

Agent 可以：

```text
查询
分析
关联
推理
建议
```

Engineer 决定：

```text
是否 Hold
是否 Release
是否 Disable Tool
是否 Change Recipe
是否执行 PM
是否关闭 Case
```

---

# 26. Agent 状态机

建议定义：

```text
CREATED
   ↓
CONTEXT_LOADING
   ↓
INVESTIGATING
   ↓
ANALYZING
   ↓
GENERATING_REPORT
   ↓
WAITING_ENGINEER_REVIEW
   ↓
COMPLETED
```

异常：

```text
FAILED
TIMEOUT
PARTIAL_RESULT
CANCELLED
```

---

# 27. Streaming

前端推荐：

```text
Vue3
  ↓
SSE
  ↓
Agent Gateway
  ↓
Agent
```

事件：

```text
analysis_started

context_loaded

tool_call_started

tool_call_completed

finding_generated

hypothesis_generated

recommendation_generated

analysis_completed
```

例如：

```json
{
  "event": "finding_generated",
  "data": {
    "type": "SPC",
    "message": "Pressure exceeded 3σ limit",
    "source": "SPC"
  }
}
```

---

# 28. Agent API

## POST /api/ai/case-analysis

```json
{
  "caseId": "CASE001"
}
```

返回：

```json
{
  "taskId": "AI-20260918-001",
  "status": "RUNNING"
}
```

---

## GET /api/ai/case-analysis/{taskId}/stream

SSE：

```text
event: analysis_started

event: context_loaded

event: tool_call_started

event: tool_call_completed

event: finding_generated

event: hypothesis_generated

event: report_generated

event: completed
```

---

## GET /api/ai/case-analysis/{taskId}

用于重新进入页面。

---

## POST /api/ai/case-analysis/{taskId}/feedback

```json
{
  "helpful": true,
  "rootCauseCorrect": true,
  "comment": "Root cause confirmed by engineer."
}
```

---

# 29. 数据模型

## CaseAnalysisTask

```text
id
caseId
status
startedAt
completedAt
agentVersion
modelVersion
createdBy
```

## CaseAnalysisFinding

```text
id
taskId
type
title
description
source
sourceId
timestamp
confidence
```

## CaseAnalysisHypothesis

```text
id
taskId
rootCause
confidence
supportingEvidence
contradictingEvidence
```

## CaseAnalysisRecommendation

```text
id
taskId
type
action
priority
reason
```

---

# 30. Agent Tool Registry

建议建立统一工具注册中心。

```text
Tool Registry

Tool Name
Description
Input Schema
Output Schema
Permission
Timeout
Data Source
Owner
Version
```

例如：

```text
getToolAlarm

Description:
Retrieve equipment alarm events for a specified tool
and time range.

Input:
toolId
startTime
endTime

Output:
alarmId
alarmCode
alarmMessage
timestamp
severity
```

这样以后增加工具不需要修改 Agent 核心逻辑。

---

# 31. 权限体系

Agent 权限必须继承现有平台权限。

```text
User
 ↓
Platform Permission
 ↓
Agent Permission
 ↓
Tool Permission
 ↓
Data Permission
```

例如：

PE：

```text
Lot Read ✓
Tool Read ✓
SPC Read ✓
FDC Read ✓
Recipe Read ✓
```

某些敏感 Recipe 数据：

```text
Recipe Detail ✕
```

Agent 不能因为是 AI 就绕过原系统权限。

---

# 32. 数据安全

所有 Agent Tool 调用必须记录：

```text
User
Case
Agent
Tool
Input
Output
Timestamp
```

形成：

```text
Audit Log
```

例如：

```text
User: engineer001
Case: CASE001
Tool: getFDCData
Time: 14:32
Reason: Case Investigation
```

---

# 33. Agent 可观测性

需要记录：

```text
Agent Execution

Task ID
Case ID
User
Model
Prompt Version
Tool Calls
Token Usage
Latency
Errors
Final Result
Engineer Feedback
```

重点监控：

### Agent Latency

```text
Context Loading
Tool Calling
LLM Reasoning
Report Generation
```

### Tool Success Rate

```text
Tool Success
Tool Timeout
Tool Error
```

### Analysis Quality

```text
Evidence Accuracy
Root Cause Accuracy
Recommendation Accuracy
Engineer Acceptance
```

---

# 34. 防止 Agent 幻觉

V1 必须建立以下规则。

## Rule 1

没有数据：

```text
不要推断为事实
```

必须输出：

```text
Insufficient Evidence
```

---

## Rule 2

所有关键结论尽量绑定数据来源。

```text
Conclusion
↓
Evidence
↓
Source
```

---

## Rule 3

区分：

```text
Observed
Inferred
Hypothesis
Recommendation
```

例如：

```text
Observed:
Pressure exceeded 3σ.

Inferred:
Pressure abnormality temporally correlates
with the yield drop.

Hypothesis:
Chamber pressure drift may have contributed
to the yield loss.

Recommendation:
Check chamber pressure sensor calibration.
```

---

# 35. Case Analysis Report 标准结构

最终统一输出：

```text
1. Case Summary

2. Impact

3. Timeline

4. Key Findings

5. Data Evidence

6. Correlation Analysis

7. Potential Root Causes

8. Historical Similar Cases

9. Recommended Actions

10. Uncertainties

11. Engineer Feedback
```

---

# 36. Timeline

建议加入非常重要的时间线。

例如：

```text
13:40
LOT entered ETCH01

14:05
Recipe RCP100 loaded

14:12
Pressure started increasing

14:18
SPC warning

14:23
Pressure exceeded 3σ

14:26
FDC alarm

14:31
Yield abnormality detected

14:35
Case created
```

这对于工程师判断因果关系非常重要。

---

# 37. Correlation View

可以设计一个 AI Relationship Graph：

```text
                 Recipe
                   │
                   │
                   ▼
Lot ──────────── Tool
│                 │
│                 │
▼                 ▼
Wafer           FDC
│                 │
│                 ▼
└────────────── SPC
                  │
                  ▼
                 Case
```

点击节点查看原始数据。

这会让 Agent 从“聊天工具”变成真正的工程分析工具。

---

# 38. AI Analysis 与现有 Case Book 联动

结合现有 PE Duty 的 Case Book 能力，可以进一步设计：

```text
Case
 ↓
AI Analysis
 ↓
Analysis Report
 ↓
Save to Case Book
```

Case Book 可以记录：

```text
Case
AI Analysis
Root Cause
Evidence
Engineer Conclusion
Final Resolution
```

最终形成：

> **Case → AI Investigation → Engineer Resolution → Organizational Knowledge**

这会成为 Agent 长期学习的重要数据资产。

---

# 39. AI Analysis 与 Case Book 的闭环

长期可以形成：

```text
Historical Cases
       ↓
Knowledge Base
       ↓
Agent Investigation
       ↓
Current Case
       ↓
Engineer Resolution
       ↓
New Historical Case
       ↓
Knowledge Base
```

即：

**Case → Knowledge → Agent → Case**

形成制造工程知识闭环。

---

# 40. V1 MVP 范围

第一版不要试图覆盖所有半导体异常。

建议先选择：

## MVP Case

**Yield Drop**

并限制：

```text
Lot
Wafer
Tool
Recipe
SPC
FDC
Historical Case
```

Agent 能力：

```text
✓ Case Understanding
✓ Context Loading
✓ Tool Calling
✓ Historical Case Retrieval
✓ Timeline
✓ Evidence
✓ Correlation
✓ Root Cause Hypothesis
✓ Recommendation
✓ Streaming
✓ Engineer Feedback
```

---

# 41. V1 暂不实现

暂时不做：

```text
✕ 自动 Hold Lot
✕ 自动 Release Lot
✕ 自动修改 Recipe
✕ 自动 Disable Tool
✕ 自动执行 MES 操作
✕ 完全自主 Agent
```

原因：

制造系统属于高风险生产环境。

第一阶段应该让 Agent：

> **Observe → Investigate → Recommend**

而不是：

> **Observe → Decide → Execute**

---

# 42. V2

扩展 Case 类型：

```text
Yield Drop
SPC Alarm
FDC Alarm
Tool Down
Lot Hold
Wafer Abnormal
Recipe Abnormal
```

增加：

```text
Multi-Agent
Advanced Correlation
Knowledge Graph
Case Similarity
Root Cause Ranking
Automatic Report
```

---

# 43. V3

进入 Agentic Manufacturing：

```text
Case
 ↓
Agent
 ↓
Investigation
 ↓
Recommendation
 ↓
Engineer Approval
 ↓
System Action
 ↓
Verification
```

例如：

```text
Agent:
Recommend Hold LOT001

Engineer:
Approve

System:
Execute Hold

Agent:
Monitor subsequent data

Agent:
Verify issue resolved
```

最终形成：

**Human-in-the-loop Manufacturing Agent**

---

# 44. 多 Agent 架构演进

当单 Agent 复杂度增加以后，可以拆分：

```text
                 PE Supervisor Agent
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     Lot Agent       Tool Agent      Process Agent
          │              │              │
          ▼              ▼              ▼
     Wafer Agent      FDC Agent       SPC Agent
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Root Cause Agent
                         │
                         ▼
                Recommendation Agent
```

但是：

> **V1 不建议一开始就做 Multi-Agent。**

先建立稳定的 Tool + Context + Investigation + Evidence 架构。

---

# 45. 技术架构建议

```text
Frontend
Vue3 + Arco Design Vue
        │
        │ SSE
        ▼
AI Gateway
        │
        ▼
Agent Runtime
        │
 ┌──────┼───────────┐
 ▼      ▼           ▼
LLM    Memory      Planner
 │
 ▼
Tool Router
 │
 ├── MES
 ├── SPC
 ├── FDC
 ├── Equipment
 ├── Recipe
 └── Case
        │
        ▼
Knowledge / Vector DB
```

---

# 46. LLM / JEV 模型层

模型层建议做成可替换架构：

```text
                    Agent Runtime
                         │
                  Model Gateway
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        JEV            GPT            Local LLM
```

这样不会让 PE Agent 和某个具体模型强绑定。

模型负责：

```text
理解
规划
推理
总结
```

业务系统负责：

```text
真实数据
权限
执行
审计
```

这是整个系统非常重要的边界。

---

# 47. Prompt Architecture

不要使用一个超长 Prompt。

建议拆成：

```text
System Prompt
      +
Domain Prompt
      +
Case Context
      +
Tool Description
      +
Investigation Plan
      +
Retrieved Knowledge
      +
Tool Results
      +
Output Schema
```

---

# 48. Agent Output Schema

建议最终强制 JSON Schema。

```json
{
  "summary": {},
  "impact": {},
  "timeline": [],
  "findings": [],
  "evidence": [],
  "hypotheses": [],
  "similarCases": [],
  "recommendations": [],
  "uncertainties": []
}
```

前端负责渲染。

这样比让 LLM 直接输出 HTML / Markdown 更稳定。

---

# 49. 前端组件结构

建议：

```text
CaseDashboard
│
├── CaseTable
│
│   └── AIAnalysisButton
│
└── CaseAnalysisDrawer
    │
    ├── AnalysisHeader
    ├── CaseSummary
    ├── InvestigationProgress
    ├── Timeline
    ├── KeyFindings
    ├── EvidencePanel
    ├── CorrelationGraph
    ├── RootCausePanel
    ├── SimilarCases
    ├── RecommendationPanel
    └── FeedbackPanel
```

推荐使用 Drawer，而不是 Modal。

因为最终分析结果可能比较长。

---

# 50. 用户体验原则

## 原则 1

AI 分析不能让用户“等黑屏”。

必须实时显示：

```text
正在读取 Case...
正在分析 Lot...
正在查询 Tool...
正在分析 SPC...
正在查询历史 Case...
正在建立关联...
```

---

## 原则 2

不要只给结论。

必须：

```text
Conclusion
+
Evidence
+
Source
```

---

## 原则 3

AI 不是最终决策者。

UI 上明确区分：

```text
AI Finding
AI Hypothesis
Engineer Decision
```

---

# 51. 性能指标

MVP 建议目标：

| 指标           |    目标 |
| ------------ | ----: |
| Case Context |  < 2s |
| 首次 AI 输出     |  < 3s |
| 普通分析         | < 30s |
| 复杂分析         | < 60s |
| Tool Timeout | < 10s |
| SSE 断线恢复     |    支持 |
| Analysis 成功率 | > 95% |

实际指标需要根据企业内部数据接口性能进一步调整。

---

# 52. AI 质量指标

不要只看：

```text
用户觉得回答不错
```

需要建立专业指标。

### Evidence Accuracy

证据是否真实。

### Root Cause Accuracy

最终根因与工程师确认结果的一致性。

### Recommendation Acceptance

工程师是否采纳建议。

### Investigation Efficiency

AI 是否减少人工查询步骤。

### Time To Resolution

Case 从创建到解决的平均时间。

---

# 53. 最重要的产品 KPI

建议最终关注：

## Case Investigation Time

例如：

```text
Before Agent

平均 30 min / Case

After Agent

平均 10 min / Case
```

目标不是：

> “AI 回答得多聪明。”

而是：

> **工程师处理一个 Case 是否明显更快、更有证据、更标准化。**

---

# 54. MVP 成功标准

如果 V1 能做到：

```text
工程师看到 Case
        ↓
点击 AI Analysis
        ↓
30~60 秒内得到完整调查结果
        ↓
自动展示：
    Case Summary
    Timeline
    Key Findings
    Evidence
    Similar Cases
    Root Cause Hypothesis
    Recommended Actions
        ↓
工程师确认 / 修正
        ↓
结果进入 Case Book
```

那么第一阶段就已经具备产品价值。

---

# 55. 最终产品形态

最终 PE Duty Dashboard 会从：

```text
传统 Dashboard

Case List
Tool Status
Lot Status
SPC
FDC
Case Book
```

逐渐演进成：

```text
                PE Intelligence Layer
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   Case Agent       Tool Agent       Process Agent
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                  Engineer Copilot
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Analyze         Explain        Recommend
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Engineer Decision
```

---

# 56. 产品演进路线

```text
Phase 1
AI Case Analysis
        ↓
Phase 2
AI Investigation
        ↓
Phase 3
AI Root Cause Analysis
        ↓
Phase 4
AI Recommendation
        ↓
Phase 5
Human-in-the-loop Action
        ↓
Phase 6
Closed-loop Manufacturing Agent
```

最终目标：

> **不是在 PE Duty 里面塞一个 ChatGPT，而是在 PE Duty 里面建立一个真正理解 Case、Lot、Wafer、Tool、Recipe、SPC、FDC 和工程知识的数字工程助手。**

---

# 57. 一句话产品定义

**PE Case Analysis Agent 是一个嵌入 PE Duty / Engineer Platform 的半导体制造领域 Agent，通过自动理解 Case、调用制造数据、检索历史案例、建立数据关联并生成证据链，辅助工程师完成异常调查、根因分析和处置决策。**

---

# 58. 产品核心架构总结

最终可以把整个产品浓缩成下面这张架构图：

```text
                         PE DUTY / ENGINEER
                                │
                                ▼
                        ┌───────────────┐
                        │  CASE LIST    │
                        └───────┬───────┘
                                │
                         AI Analysis
                                │
                                ▼
                   ┌─────────────────────┐
                   │    CASE AGENT       │
                   │                     │
                   │ Context Manager     │
                   │ Investigation       │
                   │ Planner             │
                   │ Tool Router         │
                   │ Evidence Engine     │
                   │ RCA Engine          │
                   │ Recommendation      │
                   └─────────┬───────────┘
                             │
              ┌──────────────┼───────────────┐
              ▼              ▼               ▼
           MES/Data       Knowledge       Historical
            Tools           Base            Cases
              │              │               │
       ┌──────┼──────┐       │               │
       ▼      ▼      ▼       ▼               ▼
      LOT    TOOL   SPC     SOP            Case
      WAF    FDC   RECIPE   Guide          Book
              │
              ▼
       ┌─────────────────┐
       │ Evidence Graph  │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ AI Analysis     │
       │ Report          │
       ├─────────────────┤
       │ Summary         │
       │ Impact          │
       │ Timeline        │
       │ Findings        │
       │ Evidence        │
       │ Root Cause      │
       │ Similar Cases   │
       │ Recommendation  │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Engineer Review │
       └────────┬────────┘
                │
          Confirm / Correct
                │
                ▼
            CASE BOOK
                │
                ▼
        Manufacturing Knowledge
```

**核心闭环：**

**Case → Context → Investigation → Evidence → Root Cause → Recommendation → Engineer Decision → Case Book → Knowledge**

这就是整个 PE Agent 最值得做成产品壁垒的地方。
