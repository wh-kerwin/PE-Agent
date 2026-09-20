# Evidence Model

## Evidence Object

- evidenceId
- sourceType
- sourceId
- relatedEntity
- metric
- value
- unit
- timestamp
- retrievalTime
- status
- rawRef

## Evidence Status

VERIFIED
PARTIAL
UNAVAILABLE
CONFLICTING

## Evidence Graph

节点：
Case / Lot / Wafer / Tool / Recipe / Parameter / Alarm / SPC / FDC / Historical Case / Knowledge

边：
AFFECTS
OCCURRED_BEFORE
CORRELATES_WITH
SAME_AS
DIFFERS_FROM
SUPPORTS
CONTRADICTS

## Rule

每个高价值 Hypothesis 至少应该能回溯到一个或多个 Evidence。

Evidence 不等于 Root Cause。
