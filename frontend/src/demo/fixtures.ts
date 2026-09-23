import type { AnalysisReport, TaskEnvelope } from '@/types'

export const DEMO_CASE_ID = 'SYN-CASE-PRESSURE-001'
export const DEMO_CASE_VERSION = '1'

export const demoReport: AnalysisReport = {
  schemaVersion: '1.0.0',
  reportId: 'RPT-ANA-001-V1',
  taskId: 'ANA-20260920-001',
  reportVersion: 1,
  caseSnapshot: { caseId: DEMO_CASE_ID, caseVersion: DEMO_CASE_VERSION, caseType: 'YIELD_DROP' },
  generatedAt: '2026-09-20T01:36:12Z',
  model: { provider: 'typesafe', requestedModel: 'jev-1.13.0', resolvedModel: 'jev-1.13.0', questionSetVersion: 'yield-drop-jev-v1.0.0' },
  summary: {
    title: 'LOT001 良率下降分析',
    overview: '良率下降 14 个百分点，与 ETCH01 腔体压力异常在时间上相关。该结论仍是待工程验证的假设。',
    severity: 'HIGH',
  },
  impact: {
    yield: { observedPercent: 82, baselinePercent: 96, absoluteDropPercentagePoints: 14 },
    affectedLots: ['LOT001'],
    affectedWafers: ['LOT001-W03', 'LOT001-W04'],
    affectedTools: ['ETCH01'],
  },
  timeline: [
    { eventId: 'TL-01', occurredAt: '2026-09-20T01:18:00Z', title: '检测到压力漂移', evidenceIds: ['EV-FDC-01'] },
    { eventId: 'TL-02', occurredAt: '2026-09-20T01:23:00Z', title: 'SPC 超出控制限', evidenceIds: ['EV-SPC-01'] },
    { eventId: 'TL-03', occurredAt: '2026-09-20T01:31:00Z', title: '记录良率结果', evidenceIds: ['EV-YIELD-01'] },
  ],
  findings: [
    { findingId: 'F-01', level: 'OBSERVED', title: '良率低于基线', description: 'LOT001 比匹配基线低 14 个百分点。', evidenceIds: ['EV-YIELD-01'] },
    { findingId: 'F-02', level: 'INFERRED', title: '设备特异性关联', description: '受影响设备出现压力异常，而匹配的同类设备仍处于基线范围。', evidenceIds: ['EV-SPC-01', 'EV-FDC-01', 'EV-PEER-01'] },
  ],
  evidence: [
    { evidenceId: 'EV-YIELD-01', kind: 'YIELD', observation: 'LOT001 良率为 82.0%，匹配基线为 96.0%。', source: { system: 'YIELD', sourceId: 'YLD-001' }, entityRefs: [{ type: 'LOT', id: 'LOT001' }], eventTime: '2026-09-20T01:31:00Z', retrievedAt: '2026-09-20T01:36:01Z', quality: 'VERIFIED', rawRef: '/api/ai/source-links/EV-YIELD-01', unit: '%' },
    { evidenceId: 'EV-SPC-01', kind: 'SPC', observation: '腔体压力在 01:23 UTC 超出有效上控制限。', source: { system: 'SPC', sourceId: 'SPC-889' }, entityRefs: [{ type: 'TOOL', id: 'ETCH01' }, { type: 'PARAMETER', id: 'CHAMBER_PRESSURE' }], eventTime: '2026-09-20T01:23:00Z', retrievedAt: '2026-09-20T01:36:03Z', quality: 'VERIFIED', rawRef: '/api/ai/source-links/EV-SPC-01', unit: 'Torr' },
    { evidenceId: 'EV-FDC-01', kind: 'FDC', observation: '良率结果产生前，腔体压力比匹配运行中位数高 8.2%。', source: { system: 'FDC', sourceId: 'FDC-221' }, entityRefs: [{ type: 'TOOL', id: 'ETCH01' }, { type: 'PARAMETER', id: 'CHAMBER_PRESSURE' }], eventTime: '2026-09-20T01:18:00Z', retrievedAt: '2026-09-20T01:36:04Z', quality: 'VERIFIED', rawRef: '/api/ai/source-links/EV-FDC-01', unit: '%' },
    { evidenceId: 'EV-PEER-01', kind: 'YIELD', observation: 'ETCH02 上使用 RCP100 的匹配运行保持在良率基线内。', source: { system: 'YIELD', sourceId: 'YLD-PEER-31' }, entityRefs: [{ type: 'TOOL', id: 'ETCH02' }, { type: 'RECIPE', id: 'RCP100' }], eventTime: '2026-09-20T00:58:00Z', retrievedAt: '2026-09-20T01:36:05Z', quality: 'VERIFIED', rawRef: '/api/ai/source-links/EV-PEER-01' },
    { evidenceId: 'EV-HIST-01', kind: 'HISTORICAL_CASE', observation: '历史 Case 具有相同设备系列和压力漂移症状。', source: { system: 'CASE_BOOK', sourceId: 'CASE-20260802-014' }, entityRefs: [{ type: 'TOOL', id: 'ETCH01' }], eventTime: '2026-08-02T04:00:00Z', retrievedAt: '2026-09-20T01:36:06Z', quality: 'VERIFIED', rawRef: '/api/ai/source-links/EV-HIST-01' },
  ],
  correlations: [
    { correlationId: 'C-01', type: 'TEMPORAL', description: '压力漂移和 SPC 违规先于良率结果。', evidenceIds: ['EV-FDC-01', 'EV-SPC-01', 'EV-YIELD-01'] },
    { correlationId: 'C-02', type: 'TOOL', description: '匹配的同类设备没有出现同样的良率损失。', evidenceIds: ['EV-PEER-01', 'EV-YIELD-01'] },
  ],
  hypotheses: [{
    hypothesisId: 'H-01', title: '腔体压力漂移可能导致良率损失', confidenceLevel: 'HIGH',
    supportingEvidenceIds: ['EV-SPC-01', 'EV-FDC-01', 'EV-PEER-01'], contradictingEvidenceIds: [], missingEvidence: ['校准后的验证运行'],
    modelAssessment: { questionId: 'pressure_drift_support', primitive: 'score', answer: 2.72, distribution: { INSUFFICIENT: 0.01, WEAK: 0.04, MIXED: 0.17, STRONG: 0.78 }, confidence: 0.71, resolvedModel: 'jev-1.13.0' },
  }],
  similarCases: [{ caseId: 'CASE-20260802-014', similarityReason: '相同设备系列和压力漂移症状；历史结果仅作为支持上下文。', evidenceId: 'EV-HIST-01' }],
  recommendations: [
    { recommendationId: 'REC-01', category: 'INVESTIGATION', action: '验证 ETCH01 腔体压力传感器校准并检查对应维护记录。', reason: '当前 Case 的 SPC 和 FDC 证据支持检查压力路径。', evidenceIds: ['EV-SPC-01', 'EV-FDC-01'], requiresEngineerDecision: true },
    { recommendationId: 'REC-02', category: 'FOLLOW_UP', action: '将下一次获授权的验证运行与同一匹配基线比较。', reason: '确认该假设前需要校准后运行结果。', evidenceIds: ['EV-YIELD-01', 'EV-PEER-01'], requiresEngineerDecision: true },
  ],
  uncertainties: [{ uncertaintyId: 'U-01', description: '尚无校准后的验证运行。', impact: '压力因素尚不能确认为根因。', relatedEvidenceIds: ['EV-SPC-01', 'EV-FDC-01'] }],
}

export function demoTask(status: TaskEnvelope['status'] = 'COMPLETED'): TaskEnvelope {
  return {
    taskId: demoReport.taskId,
    caseId: demoReport.caseSnapshot.caseId,
    caseVersion: demoReport.caseSnapshot.caseVersion,
    status,
    phase: status === 'COMPLETED' || status === 'PARTIAL_RESULT' ? 'GENERATING_REPORT' : 'INVESTIGATING',
    progress: status === 'COMPLETED' || status === 'PARTIAL_RESULT' ? 100 : 42,
    reviewStatus: 'NOT_REVIEWED',
    warnings: status === 'PARTIAL_RESULT' ? [{ code: 'FDC_UNAVAILABLE', source: 'FDC', message: 'FDC 明细部分不可用；现有 SPC 与良率证据仍可读取。' }] : [],
    latestEventId: '8',
    reportVersion: status === 'COMPLETED' || status === 'PARTIAL_RESULT' ? 1 : null,
    report: status === 'COMPLETED' || status === 'PARTIAL_RESULT' ? demoReport : null,
    createdAt: '2026-09-20T01:35:01Z',
    completedAt: status === 'COMPLETED' || status === 'PARTIAL_RESULT' ? '2026-09-20T01:36:12Z' : null,
  }
}
