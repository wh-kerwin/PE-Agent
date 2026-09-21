import type {
  AnalysisEvent,
  AnalysisEventType,
  AnalysisReport,
  ApiErrorBody,
  CaseAnalysisClient,
  CaseBookArchive,
  CreateAnalysisRequest,
  CreateAnalysisResponse,
  EngineerReview,
  EngineerReviewInput,
  StreamOptions,
  TaskEnvelope,
} from '@/types'
import { CaseAnalysisApiError } from '@/types'

export interface CaseAnalysisClientOptions {
  baseUrl?: string
  fetch?: typeof globalThis.fetch
  credentials?: RequestCredentials
  headers?: () => HeadersInit | Promise<HeadersInit>
}

const EVENT_TYPES: AnalysisEventType[] = [
  'analysis_started', 'phase_changed', 'tool_started', 'tool_completed', 'tool_failed',
  'evidence_added', 'report_generated', 'analysis_completed', 'analysis_partial',
  'analysis_failed', 'analysis_cancelled', 'heartbeat',
]

export function createCaseAnalysisClient(options: CaseAnalysisClientOptions = {}): CaseAnalysisClient {
  const baseUrl = (options.baseUrl ?? '/api/ai/case-analysis').replace(/\/$/, '')
  const requestFetch = options.fetch ?? globalThis.fetch.bind(globalThis)
  const credentials = options.credentials ?? 'same-origin'

  async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
    const hostHeaders = await options.headers?.()
    const response = await requestFetch(resolveUrl(baseUrl, url), {
      ...init,
      credentials,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...hostHeaders,
        ...init.headers,
      },
    })
    if (!response.ok) throw await toApiError(response)
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  return {
    createOrResume: (input: CreateAnalysisRequest) => request<CreateAnalysisResponse>('', {
      method: 'POST', body: JSON.stringify(input),
    }),
    getTask: (taskId: string) => request<TaskEnvelope>(`/${encodeURIComponent(taskId)}`),
    async getLatestTask(caseId: string) {
      try {
        return await request<TaskEnvelope>(`?caseId=${encodeURIComponent(caseId)}&latest=true`)
      } catch (error) {
        if (error instanceof CaseAnalysisApiError && error.status === 404) return null
        throw error
      }
    },
    getReport: (taskId: string, reportVersion?: number, reportUrl?: string) => {
      const fallback = `/${encodeURIComponent(taskId)}/report${reportVersion ? `?version=${reportVersion}` : ''}`
      return request<AnalysisReport>(safeReportUrl(reportUrl, baseUrl) ?? fallback)
    },
    async streamTask(taskId: string, streamOptions: StreamOptions) {
      const response = await requestFetch(resolveUrl(baseUrl, `/${encodeURIComponent(taskId)}/stream`), {
        method: 'GET',
        credentials,
        headers: {
          Accept: 'text/event-stream',
          ...(streamOptions.lastEventId ? { 'Last-Event-ID': streamOptions.lastEventId } : {}),
          ...(await options.headers?.()),
        },
        ...(streamOptions.signal ? { signal: streamOptions.signal } : {}),
      })
      if (!response.ok) throw await toApiError(response)
      if (!response.body) throw new CaseAnalysisApiError(0, 'STREAM_UNAVAILABLE', '浏览器未提供事件流。', true)

      streamOptions.onOpen()
      try {
        await parseEventStream(response.body, async (raw) => {
          if (!raw.data || !EVENT_TYPES.includes(raw.event as AnalysisEventType)) return
          try {
            const parsed = JSON.parse(raw.data) as Omit<AnalysisEvent, 'type' | 'eventId'>
            await streamOptions.onEvent({ ...parsed, type: raw.event as AnalysisEventType, eventId: raw.id })
          } catch (error) {
            streamOptions.onError(error)
          }
        }, streamOptions.signal)
        streamOptions.onClosed()
      } catch (error) {
        if (!streamOptions.signal?.aborted) streamOptions.onError(error)
        throw error
      }
    },
    submitReview: (taskId: string, input: EngineerReviewInput) => request<EngineerReview>(
      `/${encodeURIComponent(taskId)}/review`, { method: 'POST', body: JSON.stringify(input) },
    ),
    archiveCaseBook: (taskId: string, reviewRevision: number, idempotencyKey: string) => request<CaseBookArchive>(
      `/${encodeURIComponent(taskId)}/casebook`, {
        method: 'POST', body: JSON.stringify({ reviewRevision, idempotencyKey }),
      },
    ),
    retryTask: (taskId: string) => request<CreateAnalysisResponse>(`/${encodeURIComponent(taskId)}/retry`, {
      method: 'POST', body: JSON.stringify({ idempotencyKey: crypto.randomUUID() }),
    }),
    cancelTask: (taskId: string) => request<TaskEnvelope>(`/${encodeURIComponent(taskId)}/cancel`, {
      method: 'POST', body: JSON.stringify({}),
    }),
  }
}

function resolveUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  if (path.startsWith('/api/')) return path
  return `${baseUrl}${path}`
}

function safeReportUrl(reportUrl: string | undefined, baseUrl: string): string | null {
  if (!reportUrl) return null
  if (reportUrl.startsWith(`${baseUrl}/`) || reportUrl.startsWith('/api/ai/case-analysis/')) return reportUrl
  return null
}

async function toApiError(response: Response): Promise<CaseAnalysisApiError> {
  let body: ApiErrorBody = {}
  try { body = await response.json() as ApiErrorBody } catch { /* response is not JSON */ }
  return new CaseAnalysisApiError(
    response.status,
    body.error?.code ?? `HTTP_${response.status}`,
    body.error?.message ?? `请求失败（${response.status}）`,
    body.error?.retryable ?? response.status >= 500,
  )
}

interface RawSseEvent { id: string; event: string; data: string }

export async function parseEventStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: RawSseEvent) => void | Promise<void>,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (!signal?.aborted) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = parseBlock(block)
        if (event) await onEvent(event)
        boundary = buffer.indexOf('\n\n')
      }
      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
}

function parseBlock(block: string): RawSseEvent | null {
  if (!block || block.startsWith(':')) return null
  let id = ''
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('id:')) id = line.slice(3).trimStart()
    else if (line.startsWith('event:')) event = line.slice(6).trimStart()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  return data.length ? { id, event, data: data.join('\n') } : null
}
