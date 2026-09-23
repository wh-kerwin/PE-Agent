export type CaseType = 'YIELD_DROP' | string
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type TaskStatus =
  | 'CREATED'
  | 'CONTEXT_LOADING'
  | 'INVESTIGATING'
  | 'ANALYZING'
  | 'GENERATING_REPORT'
  | 'COMPLETED'
  | 'PARTIAL_RESULT'
  | 'FAILED'
  | 'TIMEOUT'
  | 'CANCELLED'
export type ReviewStatus = 'NOT_REVIEWED' | 'CONFIRMED' | 'CORRECTED' | 'INCONCLUSIVE'
export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'recovering' | 'closed'

export interface CaseAnalysisSummary {
  taskId?: string
  status?: TaskStatus
  reviewStatus?: ReviewStatus
  supported?: boolean
  disabledReason?: string
}

export interface CaseAnalysisCase {
  caseId: string
  caseVersion: string
  caseType?: CaseType
  severity?: Severity
  analysisSummary?: CaseAnalysisSummary | null
}

export interface CreateAnalysisRequest {
  caseId: string
  caseVersion: string
  idempotencyKey: string
}

export interface CreateAnalysisResponse {
  taskId: string
  caseId: string
  caseVersion: string
  status: TaskStatus
  reused: boolean
  streamUrl: string
}

export interface TaskWarning {
  code?: string
  message: string
  source?: string
}

export interface TaskEventSummary {
  sequence: number
  type: AnalysisEventType
  message: string
  occurredAt: string
  state?: 'running' | 'completed' | 'failed'
}

export interface TaskEnvelope {
  taskId: string
  caseId: string
  caseVersion: string
  status: TaskStatus
  phase?: string | null
  progress?: number | null
  reviewStatus: ReviewStatus
  warnings: Array<TaskWarning | string>
  latestEventId?: string | null
  reportVersion?: number | null
  reportUrl?: string | null
  report?: AnalysisReport | null
  events?: TaskEventSummary[]
  createdAt?: string
  updatedAt?: string
  startedAt?: string | null
  completedAt?: string | null
  supersedesTaskId?: string | null
}

export interface EntityReference {
  type: 'CASE' | 'LOT' | 'WAFER' | 'TOOL' | 'CHAMBER' | 'RECIPE' | 'PARAMETER'
  id: string
}

export interface Evidence {
  evidenceId: string
  kind: 'CASE' | 'YIELD' | 'WAFER' | 'TOOL_EVENT' | 'RECIPE' | 'SPC' | 'FDC' | 'HISTORICAL_CASE'
  observation: string
  source: { system: string; sourceId: string }
  entityRefs: EntityReference[]
  eventTime: string
  retrievedAt: string
  quality: 'VERIFIED' | 'PARTIAL' | 'CONFLICTING'
  rawRef: string
  unit?: string | null
}

export interface EvidenceLinked {
  evidenceIds: string[]
}

export interface Finding extends EvidenceLinked {
  findingId: string
  level: 'OBSERVED' | 'INFERRED'
  title: string
  description: string
}

export interface ModelAssessment {
  questionId: string
  primitive: 'choice' | 'score' | 'noul'
  answer: string | number
  distribution: Record<string, number>
  confidence: number | null
  resolvedModel: string
}

export interface Hypothesis {
  hypothesisId: string
  title: string
  confidenceLevel: 'LOW' | 'MEDIUM' | 'HIGH'
  supportingEvidenceIds: string[]
  contradictingEvidenceIds: string[]
  missingEvidence: string[]
  modelAssessment: ModelAssessment
}

export interface Recommendation extends EvidenceLinked {
  recommendationId: string
  category: 'IMMEDIATE' | 'INVESTIGATION' | 'FOLLOW_UP'
  action: string
  reason: string
  requiresEngineerDecision: true
}

export interface AnalysisReport {
  schemaVersion: '1.0.0'
  reportId: string
  taskId: string
  reportVersion: number
  caseSnapshot: { caseId: string; caseVersion: string; caseType: 'YIELD_DROP' }
  generatedAt: string
  model: {
    provider: string
    requestedModel: string
    resolvedModel: string
    questionSetVersion: string
  }
  summary: { title: string; overview: string; severity: Severity }
  impact: {
    yield: { observedPercent: number; baselinePercent: number; absoluteDropPercentagePoints: number }
    affectedLots: string[]
    affectedWafers: string[]
    affectedTools: string[]
  }
  timeline: Array<{ eventId: string; occurredAt: string; title: string; evidenceIds: string[] }>
  findings: Finding[]
  evidence: Evidence[]
  correlations: Array<{ correlationId: string; type: string; description: string; evidenceIds: string[] }>
  hypotheses: Hypothesis[]
  similarCases: Array<{ caseId: string; similarityReason: string; evidenceId: string }>
  recommendations: Recommendation[]
  uncertainties: Array<{ uncertaintyId: string; description: string; impact: string; relatedEvidenceIds: string[] }>
  expression?: {
    provider: 'openai-compatible'
    requestedModel: string
    resolvedModel: string
    text: string
    nonAuthoritative: true
    usage: { inputTokens: number; outputTokens: number; latencyMs: number }
  }
}

export interface EngineerReviewInput {
  reportVersion: number
  reviewStatus: Exclude<ReviewStatus, 'NOT_REVIEWED'>
  helpful: boolean | null
  confirmedHypothesisId: string | null
  actualRootCause: string | null
  comment: string | null
  idempotencyKey: string
}

export interface EngineerReview extends EngineerReviewInput {
  taskId: string
  reviewRevision: number
  createdAt?: string
}

export interface CaseBookArchive {
  archiveId: string
  status: 'PENDING' | 'ARCHIVED' | 'FAILED'
  reviewRevision: number
  message?: string
}

export type AnalysisEventType =
  | 'analysis_started'
  | 'phase_changed'
  | 'tool_started'
  | 'tool_completed'
  | 'tool_failed'
  | 'evidence_added'
  | 'report_generated'
  | 'analysis_completed'
  | 'analysis_partial'
  | 'analysis_failed'
  | 'analysis_cancelled'
  | 'heartbeat'

export interface AnalysisEvent {
  schemaVersion: string
  taskId: string
  sequence: number
  occurredAt: string
  payload: {
    phase?: string
    progress?: number
    message?: string
    toolName?: string
    reportVersion?: number
    reportUrl?: string
    [key: string]: unknown
  }
  type: AnalysisEventType
  eventId?: string
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    retryable?: boolean
    traceId?: string
    details?: Record<string, unknown>
  }
}

export class CaseAnalysisApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly retryable = false,
  ) {
    super(message)
    this.name = 'CaseAnalysisApiError'
  }
}

export interface StreamHandlers {
  onOpen(): void
  onEvent(event: AnalysisEvent): void | Promise<void>
  onError(error: unknown): void
  onClosed(): void
}

export interface StreamOptions extends StreamHandlers {
  lastEventId?: string | null
  signal?: AbortSignal
}

export interface CaseAnalysisClient {
  createOrResume(input: CreateAnalysisRequest): Promise<CreateAnalysisResponse>
  getTask(taskId: string): Promise<TaskEnvelope>
  getLatestTask(caseId: string): Promise<TaskEnvelope | null>
  getReport(taskId: string, reportVersion?: number, reportUrl?: string): Promise<AnalysisReport>
  streamTask(taskId: string, options: StreamOptions): Promise<void>
  submitReview(taskId: string, input: EngineerReviewInput): Promise<EngineerReview>
  archiveCaseBook(taskId: string, reviewRevision: number, idempotencyKey: string): Promise<CaseBookArchive>
  retryTask(taskId: string): Promise<CreateAnalysisResponse>
  cancelTask(taskId: string): Promise<TaskEnvelope>
}

export interface CaseAnalysisHost {
  onAuthRequired?: () => void | Promise<void>
  onAccessDenied?: (caseId: string) => void
  openSource: (rawRef: string) => void | Promise<void>
  onCaseVersionConflict?: (caseId: string) => void | Promise<void>
}

export const TERMINAL_STATUSES: readonly TaskStatus[] = [
  'COMPLETED', 'PARTIAL_RESULT', 'FAILED', 'TIMEOUT', 'CANCELLED',
]

export function isTerminalStatus(status: TaskStatus): boolean {
  return TERMINAL_STATUSES.includes(status)
}
