import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCaseAnalysisStore } from './caseAnalysis'
import type { AnalysisEvent, CaseAnalysisClient, TaskEnvelope } from '@/types'

function task(caseId: string, taskId: string): TaskEnvelope {
  return { taskId, caseId, caseVersion: '1', status: 'INVESTIGATING', phase: 'INVESTIGATING', progress: 10, reviewStatus: 'NOT_REVIEWED', warnings: [], latestEventId: '1', reportVersion: null }
}

function client(overrides: Partial<CaseAnalysisClient> = {}): CaseAnalysisClient {
  return {
    createOrResume: vi.fn(), getTask: vi.fn(), getLatestTask: vi.fn(), getReport: vi.fn(),
    streamTask: vi.fn(() => new Promise(() => undefined)), submitReview: vi.fn(), archiveCaseBook: vi.fn(),
    retryTask: vi.fn(), cancelTask: vi.fn(), ...overrides,
  } as CaseAnalysisClient
}

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
})

describe('case analysis store', () => {
  it('deduplicates events by task and sequence without accumulating progress', async () => {
    const api = client({ getLatestTask: vi.fn().mockResolvedValue(task('CASE-1', 'TASK-1')) })
    const store = useCaseAnalysisStore()
    store.configure(api, { openSource: vi.fn() })
    await store.openCaseAnalysis({ caseId: 'CASE-1', caseVersion: '1' })

    const event: AnalysisEvent = { schemaVersion: '1.0.0', taskId: 'TASK-1', sequence: 2, occurredAt: new Date().toISOString(), type: 'phase_changed', payload: { progress: 40, message: 'Checking SPC' } }
    expect(await store.applyEvent(event)).toBe(true)
    expect(await store.applyEvent({ ...event, payload: { progress: 99 } })).toBe(false)
    expect(store.activeTask?.progress).toBe(40)
    expect(store.activeTask?.events).toHaveLength(1)
  })

  it('prevents a late previous-case snapshot from replacing the current case', async () => {
    let resolveFirst!: (value: TaskEnvelope) => void
    const first = new Promise<TaskEnvelope>((resolve) => { resolveFirst = resolve })
    const api = client({
      getLatestTask: vi.fn()
        .mockReturnValueOnce(first)
        .mockResolvedValueOnce(task('CASE-2', 'TASK-2')),
    })
    const store = useCaseAnalysisStore()
    store.configure(api, { openSource: vi.fn() })

    const openingFirst = store.openCaseAnalysis({ caseId: 'CASE-1', caseVersion: '1' })
    await store.openCaseAnalysis({ caseId: 'CASE-2', caseVersion: '1' })
    resolveFirst(task('CASE-1', 'TASK-1'))
    await openingFirst

    expect(store.activeCase?.caseId).toBe('CASE-2')
    expect(store.activeTaskId).toBe('TASK-2')
    expect(store.tasksById['TASK-1']).toBeUndefined()
  })

  it('recovers an expired event cursor through the authoritative snapshot', async () => {
    const snapshot = { ...task('CASE-1', 'TASK-1'), latestEventId: '19', progress: 66 }
    const api = client({ getLatestTask: vi.fn().mockResolvedValue(task('CASE-1', 'TASK-1')), getTask: vi.fn().mockResolvedValue(snapshot) })
    const store = useCaseAnalysisStore()
    store.configure(api, { openSource: vi.fn() })
    await store.openCaseAnalysis({ caseId: 'CASE-1', caseVersion: '1' })
    await store.reconnectFrom('TASK-1')

    expect(api.getTask).toHaveBeenCalledWith('TASK-1')
    expect(store.activeTask?.latestEventId).toBe('19')
    expect(store.activeTask?.progress).toBe(66)
  })
})
