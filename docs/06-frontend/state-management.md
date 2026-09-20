# State Management

Pinia Store：

`useCaseAnalysisStore`

## State

taskId
caseId
status
plan
events
summary
impact
timeline
findings
evidence
correlations
hypotheses
similarCases
knowledgeReferences
recommendations
actions
approval
execution
verification
error

## Actions

createAnalysis
connectStream
reconnectStream
loadTask
retryAnalysis
submitFeedback
approveAction
rejectAction
refreshAction
reset

## Persistence

taskId 必须可持久化。

页面刷新：
Case → latest task → load task → reconnect stream / fetch result。
