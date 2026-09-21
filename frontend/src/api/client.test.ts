import { describe, expect, it, vi } from 'vitest'
import { createCaseAnalysisClient, parseEventStream } from './client'

function stream(value: string) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(value))
      controller.close()
    },
  })
}

describe('case analysis client', () => {
  it('parses standard SSE blocks and multiline data', async () => {
    const events: unknown[] = []
    await parseEventStream(stream(': ping\n\nid: 42\nevent: phase_changed\ndata: {"taskId":"T1",\ndata: "sequence":42}\n\n'), (event) => { events.push(event) })
    expect(events).toEqual([{ id: '42', event: 'phase_changed', data: '{"taskId":"T1",\n"sequence":42}' }])
  })

  it('sends host-provided headers and same-origin credentials without token storage', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ taskId: 'T1' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const client = createCaseAnalysisClient({ fetch: fetchMock, headers: () => ({ 'X-CSRF': 'host-value' }) })
    await client.getTask('T1')
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/case-analysis/T1', expect.objectContaining({ credentials: 'same-origin', headers: expect.objectContaining({ 'X-CSRF': 'host-value' }) }))
  })

  it('exposes structured cursor expiry errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'EVENT_CURSOR_EXPIRED', message: 'expired', retryable: false } }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    const client = createCaseAnalysisClient({ fetch: fetchMock })
    await expect(client.streamTask('T1', { onOpen: vi.fn(), onEvent: vi.fn(), onError: vi.fn(), onClosed: vi.fn() })).rejects.toMatchObject({ status: 409, code: 'EVENT_CURSOR_EXPIRED' })
  })
})
