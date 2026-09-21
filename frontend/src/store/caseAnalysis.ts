import { computed, reactive, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import type {
  AnalysisEvent,
  AnalysisReport,
  CaseAnalysisCase,
  CaseAnalysisClient,
  CaseAnalysisHost,
  CaseBookArchive,
  ConnectionStatus,
  CreateAnalysisResponse,
  EngineerReview,
  EngineerReviewInput,
  TaskEnvelope,
  TaskEventSummary,
} from '@/types'
import { CaseAnalysisApiError, isTerminalStatus } from '@/types'

const STORAGE_KEY = 'pe.case-analysis.recovery.v1'
const MAX_EVENTS = 30

interface RecoveryRecord {
  caseId: string
  taskId: string
  lastEventId: string | null
}

export const useCaseAnalysisStore = defineStore('caseAnalysis', () => {
  const client = shallowRef<CaseAnalysisClient | null>(null)
  const host = shallowRef<CaseAnalysisHost | null>(null)
  const tasksById = reactive<Record<string, TaskEnvelope>>({})
  const latestTaskByCase = reactive<Record<string, string>>({})
  const reportsByTaskVersion = reactive<Record<string, AnalysisReport>>({})
  const reviewsByTask = reactive<Record<string, EngineerReview>>({})
  const archivesByTask = reactive<Record<string, CaseBookArchive>>({})
  const lastSequenceByTask = reactive<Record<string, number>>({})
  const connectionByTask = reactive<Record<string, ConnectionStatus>>({})
  const drawerOpen = ref(false)
  const activeCase = ref<CaseAnalysisCase | null>(null)
  const activeTaskId = ref<string | null>(null)
  const loading = ref(false)
  const actionPending = ref(false)
  const reviewPending = ref(false)
  const archivePending = ref(false)
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)

  let requestEpoch = 0
  let streamAbort: AbortController | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempt = 0

  const activeTask = computed(() => activeTaskId.value ? tasksById[activeTaskId.value] ?? null : null)
  const activeReport = computed(() => {
    const task = activeTask.value
    if (!task) return null
    if (task.report) return task.report
    if (!task.reportVersion) return null
    return reportsByTaskVersion[reportKey(task.taskId, task.reportVersion)] ?? null
  })
  const activeReview = computed(() => activeTaskId.value ? reviewsByTask[activeTaskId.value] ?? null : null)
  const activeArchive = computed(() => activeTaskId.value ? archivesByTask[activeTaskId.value] ?? null : null)
  const connectionStatus = computed<ConnectionStatus>(() => activeTaskId.value
    ? connectionByTask[activeTaskId.value] ?? 'idle'
    : 'idle')

  function configure(nextClient: CaseAnalysisClient, nextHost: CaseAnalysisHost) {
    client.value = nextClient
    host.value = nextHost
  }

  async function openCaseAnalysis(caseInfo: CaseAnalysisCase, startNew = false) {
    const epoch = ++requestEpoch
    stopStream()
    drawerOpen.value = true
    activeCase.value = caseInfo
    activeTaskId.value = null
    loading.value = true
    error.value = null
    errorCode.value = null

    try {
      let task: TaskEnvelope | null = null
      if (!startNew) {
        const recovery = readRecovery()
        if (recovery?.caseId === caseInfo.caseId) task = await requiredClient().getTask(recovery.taskId)
        else task = await requiredClient().getLatestTask(caseInfo.caseId)
      }
      if (isStale(epoch, caseInfo.caseId)) return
      if (!task || startNew) {
        const created = await requiredClient().createOrResume({
          caseId: caseInfo.caseId,
          caseVersion: caseInfo.caseVersion,
          idempotencyKey: crypto.randomUUID(),
        })
        if (isStale(epoch, caseInfo.caseId)) return
        activeTaskId.value = created.taskId
        const snapshot = await requiredClient().getTask(created.taskId)
        if (isStale(epoch, caseInfo.caseId, created.taskId)) return
        task = snapshot
      }
      await acceptSnapshot(task, epoch)
    } catch (cause) {
      if (!isStale(epoch, caseInfo.caseId)) await handleError(cause, caseInfo.caseId)
    } finally {
      if (!isStale(epoch, caseInfo.caseId)) loading.value = false
    }
  }

  async function createOrResume() {
    const caseInfo = activeCase.value
    if (!caseInfo) return
    await openCaseAnalysis(caseInfo, true)
  }

  async function loadTaskSnapshot(taskId: string, epoch = requestEpoch): Promise<TaskEnvelope | null> {
    try {
      const snapshot = await requiredClient().getTask(taskId)
      if (isStale(epoch, snapshot.caseId, taskId)) return null
      await acceptSnapshot(snapshot, epoch)
      return snapshot
    } catch (cause) {
      if (!isStale(epoch, activeCase.value?.caseId, taskId)) await handleError(cause, activeCase.value?.caseId)
      return null
    }
  }

  async function acceptSnapshot(snapshot: TaskEnvelope, epoch: number) {
    if (isStale(epoch, snapshot.caseId)) return
    snapshot.warnings ??= []
    snapshot.reviewStatus ??= 'NOT_REVIEWED'
    snapshot.events = tasksById[snapshot.taskId]?.events ?? snapshot.events ?? []
    tasksById[snapshot.taskId] = snapshot
    latestTaskByCase[snapshot.caseId] = snapshot.taskId
    activeTaskId.value = snapshot.taskId
    if (snapshot.latestEventId) {
      const numeric = Number(snapshot.latestEventId)
      if (Number.isFinite(numeric)) lastSequenceByTask[snapshot.taskId] = Math.max(lastSequenceByTask[snapshot.taskId] ?? 0, numeric)
    }
    if (snapshot.report) cacheReport(snapshot.report)
    else if (snapshot.reportVersion) await fetchReport(snapshot.taskId, snapshot.reportVersion, snapshot.reportUrl ?? undefined, epoch)
    persistRecovery(snapshot.caseId, snapshot.taskId, snapshot.latestEventId ?? null)
    if (!isTerminalStatus(snapshot.status)) connectStream(snapshot.taskId, snapshot.latestEventId ?? null, epoch)
    else connectionByTask[snapshot.taskId] = 'closed'
  }

  function connectStream(taskId: string, lastEventId: string | null = null, epoch = requestEpoch) {
    stopStream()
    if (isStale(epoch, activeCase.value?.caseId, taskId) || document.visibilityState === 'hidden') return
    const controller = new AbortController()
    streamAbort = controller
    connectionByTask[taskId] = reconnectAttempt ? 'recovering' : 'connecting'
    void requiredClient().streamTask(taskId, {
      lastEventId,
      signal: controller.signal,
      onOpen: () => {
        if (!isStale(epoch, activeCase.value?.caseId, taskId)) {
          connectionByTask[taskId] = 'connected'
          reconnectAttempt = 0
        }
      },
      onEvent: async (event) => { await applyEvent(event, epoch) },
      onError: () => {
        if (!controller.signal.aborted && !isStale(epoch, activeCase.value?.caseId, taskId)) {
          connectionByTask[taskId] = 'recovering'
        }
      },
      onClosed: () => undefined,
    }).then(() => {
      if (controller.signal.aborted || isStale(epoch, activeCase.value?.caseId, taskId)) return
      const task = tasksById[taskId]
      if (task && !isTerminalStatus(task.status)) scheduleReconnect(taskId, epoch)
    }).catch(async (cause: unknown) => {
      if (controller.signal.aborted || isStale(epoch, activeCase.value?.caseId, taskId)) return
      if (cause instanceof CaseAnalysisApiError && cause.code === 'EVENT_CURSOR_EXPIRED') {
        await reconnectFrom(taskId, epoch)
      } else if (cause instanceof CaseAnalysisApiError && (cause.status === 401 || cause.status === 403)) {
        await handleError(cause, activeCase.value?.caseId)
      } else {
        scheduleReconnect(taskId, epoch)
      }
    })
  }

  async function applyEvent(event: AnalysisEvent, epoch = requestEpoch): Promise<boolean> {
    if (isStale(epoch, activeCase.value?.caseId, event.taskId)) return false
    const previous = lastSequenceByTask[event.taskId] ?? 0
    if (event.sequence <= previous) return false
    const task = tasksById[event.taskId]
    if (!task) return false

    lastSequenceByTask[event.taskId] = event.sequence
    task.latestEventId = event.eventId || String(event.sequence)
    if (event.payload.phase) task.phase = event.payload.phase
    if (typeof event.payload.progress === 'number') task.progress = event.payload.progress
    task.events = appendEvent(task.events ?? [], toEventSummary(event))
    applyTerminalEvent(task, event.type)
    persistRecovery(task.caseId, task.taskId, task.latestEventId)

    if (event.type === 'report_generated') {
      const version = Number(event.payload.reportVersion)
      if (Number.isInteger(version) && version > 0) {
        task.reportVersion = version
        await fetchReport(task.taskId, version, typeof event.payload.reportUrl === 'string' ? event.payload.reportUrl : undefined, epoch)
      } else {
        await loadTaskSnapshot(task.taskId, epoch)
      }
    } else if (isTerminalStatus(task.status)) {
      stopStream()
      await loadTaskSnapshot(task.taskId, epoch)
    }
    return true
  }

  async function reconnectFrom(taskId: string, epoch = requestEpoch) {
    connectionByTask[taskId] = 'recovering'
    const snapshot = await requiredClient().getTask(taskId)
    if (isStale(epoch, snapshot.caseId, taskId)) return
    await acceptSnapshot(snapshot, epoch)
  }

  async function fetchReport(taskId: string, version: number, reportUrl?: string, epoch = requestEpoch) {
    const key = reportKey(taskId, version)
    if (reportsByTaskVersion[key]) return reportsByTaskVersion[key]
    const report = await requiredClient().getReport(taskId, version, reportUrl)
    if (isStale(epoch, activeCase.value?.caseId, taskId)) return null
    cacheReport(report)
    return report
  }

  function cacheReport(report: AnalysisReport) {
    reportsByTaskVersion[reportKey(report.taskId, report.reportVersion)] = report
    const task = tasksById[report.taskId]
    if (task) {
      task.reportVersion = report.reportVersion
      task.report = report
    }
  }

  async function submitReview(input: Omit<EngineerReviewInput, 'idempotencyKey' | 'reportVersion'>) {
    const task = activeTask.value
    const report = activeReport.value
    if (!task || !report) return
    reviewPending.value = true
    error.value = null
    try {
      const review = await requiredClient().submitReview(task.taskId, {
        ...input,
        reportVersion: report.reportVersion,
        idempotencyKey: crypto.randomUUID(),
      })
      if (activeTaskId.value !== task.taskId) return
      reviewsByTask[task.taskId] = review
      task.reviewStatus = review.reviewStatus
    } catch (cause) {
      await handleError(cause, task.caseId)
      throw cause
    } finally {
      reviewPending.value = false
    }
  }

  async function archiveCaseBook() {
    const taskId = activeTaskId.value
    const review = taskId ? reviewsByTask[taskId] : null
    if (!taskId || !review) return
    archivePending.value = true
    try {
      const archive = await requiredClient().archiveCaseBook(taskId, review.reviewRevision, crypto.randomUUID())
      if (activeTaskId.value === taskId) archivesByTask[taskId] = archive
    } catch (cause) {
      await handleError(cause, activeCase.value?.caseId)
      throw cause
    } finally {
      archivePending.value = false
    }
  }

  async function retryAsNewTask() {
    const oldTaskId = activeTaskId.value
    if (!oldTaskId) return
    actionPending.value = true
    try {
      const created = await requiredClient().retryTask(oldTaskId)
      await activateCreatedTask(created)
    } catch (cause) {
      await handleError(cause, activeCase.value?.caseId)
    } finally {
      actionPending.value = false
    }
  }

  async function cancelTask() {
    const taskId = activeTaskId.value
    if (!taskId) return
    actionPending.value = true
    try {
      const task = await requiredClient().cancelTask(taskId)
      if (activeTaskId.value === taskId) await acceptSnapshot(task, requestEpoch)
    } catch (cause) {
      await handleError(cause, activeCase.value?.caseId)
    } finally {
      actionPending.value = false
    }
  }

  async function activateCreatedTask(created: CreateAnalysisResponse) {
    const epoch = ++requestEpoch
    stopStream()
    activeTaskId.value = created.taskId
    loading.value = true
    try { await loadTaskSnapshot(created.taskId, epoch) } finally { loading.value = false }
  }

  function closeDrawer() {
    ++requestEpoch
    stopStream()
    drawerOpen.value = false
    activeCase.value = null
    activeTaskId.value = null
    loading.value = false
    error.value = null
  }

  function stopStream() {
    streamAbort?.abort()
    streamAbort = null
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  function scheduleReconnect(taskId: string, epoch: number) {
    if (isStale(epoch, activeCase.value?.caseId, taskId) || document.visibilityState === 'hidden') return
    connectionByTask[taskId] = 'recovering'
    const delay = Math.min(1000 * 2 ** reconnectAttempt, 15_000) + Math.round(Math.random() * 400)
    reconnectAttempt += 1
    reconnectTimer = setTimeout(() => {
      const task = tasksById[taskId]
      if (task && !isTerminalStatus(task.status)) connectStream(taskId, task.latestEventId ?? null, epoch)
    }, delay)
  }

  async function handleError(cause: unknown, caseId?: string) {
    const apiError = cause instanceof CaseAnalysisApiError ? cause : null
    errorCode.value = apiError?.code ?? 'UNKNOWN'
    error.value = apiError?.message ?? '暂时无法加载分析，请稍后重试。'
    if (apiError?.status === 401 || apiError?.status === 403) {
      clearVisibleData()
      if (apiError.status === 401) await host.value?.onAuthRequired?.()
      else if (caseId) host.value?.onAccessDenied?.(caseId)
    } else if (apiError?.code === 'CASE_VERSION_CONFLICT' && caseId) {
      await host.value?.onCaseVersionConflict?.(caseId)
    }
  }

  function clearVisibleData() {
    stopStream()
    for (const key of Object.keys(tasksById)) delete tasksById[key]
    for (const key of Object.keys(reportsByTaskVersion)) delete reportsByTaskVersion[key]
    activeTaskId.value = null
    sessionStorage.removeItem(STORAGE_KEY)
  }

  function isStale(epoch: number, caseId?: string, taskId?: string): boolean {
    return epoch !== requestEpoch
      || (!!caseId && activeCase.value?.caseId !== caseId)
      || (!!taskId && activeTaskId.value !== taskId)
  }

  function onVisibilityChange() {
    const task = activeTask.value
    if (document.visibilityState === 'visible' && drawerOpen.value && task && !isTerminalStatus(task.status)) {
      connectStream(task.taskId, task.latestEventId ?? null, requestEpoch)
    } else if (document.visibilityState === 'hidden') {
      stopStream()
    }
  }

  function requiredClient(): CaseAnalysisClient {
    if (!client.value) throw new Error('Case analysis client is not configured.')
    return client.value
  }

  return {
    tasksById, latestTaskByCase, reportsByTaskVersion, reviewsByTask, connectionByTask,
    drawerOpen, activeCase, activeTaskId, activeTask, activeReport, activeReview, activeArchive,
    connectionStatus, loading, actionPending, reviewPending, archivePending, error, errorCode,
    configure, openCaseAnalysis, createOrResume, loadTaskSnapshot, connectStream, applyEvent,
    reconnectFrom, submitReview, archiveCaseBook, retryAsNewTask, cancelTask, closeDrawer,
    onVisibilityChange,
  }
})

function reportKey(taskId: string, version: number) {
  return `${taskId}:${version}`
}

function appendEvent(events: TaskEventSummary[], event: TaskEventSummary): TaskEventSummary[] {
  return [...events.filter((item) => item.sequence !== event.sequence), event]
    .sort((a, b) => a.sequence - b.sequence)
    .slice(-MAX_EVENTS)
}

function toEventSummary(event: AnalysisEvent): TaskEventSummary {
  const state = event.type === 'tool_failed' || event.type === 'analysis_failed' ? 'failed'
    : event.type === 'tool_completed' || event.type.startsWith('analysis_') && event.type !== 'analysis_started' ? 'completed'
      : 'running'
  return {
    sequence: event.sequence,
    type: event.type,
    message: String(event.payload.message ?? event.payload.toolName ?? labelForEvent(event.type)),
    occurredAt: event.occurredAt,
    state,
  }
}

function labelForEvent(type: AnalysisEvent['type']): string {
  return ({
    analysis_started: '分析已开始', phase_changed: '分析阶段已更新', tool_started: '开始查询数据',
    tool_completed: '数据查询完成', tool_failed: '数据查询未完成', evidence_added: '发现新证据',
    report_generated: '报告已生成', analysis_completed: '分析完成', analysis_partial: '部分分析完成',
    analysis_failed: '分析失败', analysis_cancelled: '分析已取消', heartbeat: '分析仍在进行',
  })[type]
}

function applyTerminalEvent(task: TaskEnvelope, type: AnalysisEvent['type']) {
  if (type === 'analysis_completed') task.status = 'COMPLETED'
  else if (type === 'analysis_partial') task.status = 'PARTIAL_RESULT'
  else if (type === 'analysis_failed') task.status = 'FAILED'
  else if (type === 'analysis_cancelled') task.status = 'CANCELLED'
}

function readRecovery(): RecoveryRecord | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY)
    return value ? JSON.parse(value) as RecoveryRecord : null
  } catch { return null }
}

function persistRecovery(caseId: string, taskId: string, lastEventId: string | null) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ caseId, taskId, lastEventId })) } catch { /* unavailable */ }
}
