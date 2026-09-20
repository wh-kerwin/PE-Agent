# Tool Registry

## Tool Categories

### Case
- getCase
- getCaseHistory
- searchCases
- getSimilarCases

### Lot
- getLotInfo
- getLotHistory
- getLotYield
- getAffectedWafers
- getLotRoute

### Wafer
- getWaferData
- getWaferMap
- getWaferMeasurements
- getWaferDefects

### Tool
- getToolStatus
- getToolAlarm
- getToolHistory
- getToolPMHistory
- getChamberStatus
- getToolUtilization

### Recipe
- getRecipeInfo
- getRecipeVersion
- getRecipeChangeHistory
- compareRecipe

### SPC
- getSPCTrend
- getSPCViolation
- getControlLimits
- getSPCRuleViolation

### FDC
- getFDCData
- getFDCAlarm
- getParameterTrend
- detectParameterDrift

### Knowledge
- searchSOP
- searchTroubleshooting
- searchCaseBook
- searchEngineeringDocs

### V3 Action
- createAction
- checkActionPermission
- requestApproval
- executeApprovedAction
- getActionStatus
- startMonitoring
- verifyActionResult

## Registry Fields

- toolId
- name
- description
- version
- inputSchema
- outputSchema
- permission
- riskLevel
- timeout
- retry
- owner
- auditLevel
- enabled
