# Prompt Architecture

## Prompt Stack

1. System
2. Domain
3. Safety
4. Case Context
5. Tool Definitions
6. Investigation Plan
7. Retrieved Evidence
8. Knowledge
9. Output Schema

## System Prompt Requirements

明确：
- Agent 身份
- 调查目标
- 禁止事项
- Evidence 要求
- 输出格式

## Dynamic Context

只注入：
- 当前 Case
- 相关实体
- 已获得 Evidence
- 当前 Plan
- 当前 Tool Result

避免将整个企业数据库塞进上下文。

## Prompt Version

所有 Prompt 必须有版本：
`pe-agent-system-v1.0`

用于 Evaluation 和 Audit。
