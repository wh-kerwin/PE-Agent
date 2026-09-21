import type { Page, Route } from '@playwright/test'
import { demoReport } from '../../src/demo/fixtures'

type Scenario = 'success' | 'partial' | 'refresh'

const baseTask = {
  taskId: demoReport.taskId,
  caseId: demoReport.caseSnapshot.caseId,
  caseVersion: demoReport.caseSnapshot.caseVersion,
  phase: 'GENERATING_REPORT',
  progress: 100,
  reviewStatus: 'NOT_REVIEWED',
  latestEventId: '9',
  reportVersion: 1,
  report: demoReport,
  warnings: [],
}

export async function installCaseAnalysisRoutes(page: Page, scenario: Scenario) {
  let latestCalls = 0

  await page.route('**/api/ai/case-analysis**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (path.endsWith('/stream')) return fulfillSse(route, scenario)
    if (path.endsWith('/review') && method === 'POST') {
      const body = request.postDataJSON()
      return json(route, { ...body, taskId: demoReport.taskId, reviewRevision: 1, createdAt: '2026-09-20T02:00:00Z' })
    }
    if (path.endsWith('/casebook') && method === 'POST') return json(route, { archiveId: 'ARCH-001', status: 'ARCHIVED', reviewRevision: 1 })
    if (path.endsWith('/report')) return json(route, demoReport)

    if (method === 'POST' && path === '/api/ai/case-analysis') {
      return json(route, { taskId: demoReport.taskId, caseId: demoReport.caseSnapshot.caseId, caseVersion: '17', status: 'CREATED', reused: false, streamUrl: `/api/ai/case-analysis/${demoReport.taskId}/stream` }, 202)
    }
    if (method === 'GET' && url.searchParams.get('latest') === 'true') {
      latestCalls += 1
      if (scenario === 'refresh' && latestCalls === 1) return json(route, runningTask())
      return json(route, scenario === 'partial' ? partialTask() : completedTask())
    }
    if (method === 'GET' && path.endsWith(`/${demoReport.taskId}`)) {
      return json(route, scenario === 'partial' ? partialTask() : completedTask())
    }
    return json(route, { error: { code: 'NOT_FOUND', message: 'Not found', retryable: false } }, 404)
  })
}

function completedTask() { return { ...baseTask, status: 'COMPLETED' } }
function partialTask() {
  return {
    ...baseTask,
    status: 'PARTIAL_RESULT',
    warnings: [{ code: 'FDC_UNAVAILABLE', source: 'FDC', message: 'FDC 明细不可用；已有 SPC 与良率证据仍可读取。' }],
  }
}
function runningTask() {
  return { ...baseTask, status: 'INVESTIGATING', phase: 'INVESTIGATING', progress: 42, reportVersion: null, report: null, latestEventId: '2' }
}

async function fulfillSse(route: Route, scenario: Scenario) {
  if (scenario !== 'refresh') return route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
  const event = (id: number, type: string, payload: object) => `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify({ schemaVersion: '1.0.0', taskId: demoReport.taskId, sequence: id, occurredAt: '2026-09-20T01:36:12Z', payload })}\n\n`
  return route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    headers: { 'Cache-Control': 'no-cache' },
    body: event(3, 'phase_changed', { phase: 'ANALYZING', progress: 68, message: '正在分析证据关联' })
      + event(4, 'report_generated', { reportVersion: 1, reportUrl: `/api/ai/case-analysis/${demoReport.taskId}/report` })
      + event(5, 'analysis_completed', { message: '分析完成' }),
  })
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}
