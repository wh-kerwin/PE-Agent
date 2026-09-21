import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/vue'
import ArcoVue from '@arco-design/web-vue'
import CaseAnalysisAction from './CaseAnalysisAction.vue'

describe('CaseAnalysisAction', () => {
  it('keeps a stable action width and emits its host-neutral open intent', async () => {
    const { emitted } = render(CaseAnalysisAction, {
      props: { caseId: 'CASE-1', caseVersion: '7' },
      global: { plugins: [ArcoVue] },
    })
    const button = screen.getByRole('button', { name: 'AI 分析 CASE-1' })
    await fireEvent.click(button)
    expect(emitted().open?.[0]).toEqual([{ caseId: 'CASE-1', caseVersion: '7', startNew: false }])
  })

  it('disables unsupported case types with an accessible reason', () => {
    render(CaseAnalysisAction, {
      props: { caseId: 'CASE-2', caseVersion: '1', analysisSummary: { supported: false, disabledReason: 'V1 仅支持 Yield Drop Case' } },
      global: { plugins: [ArcoVue] },
    })
    expect(screen.getByRole('button', { name: 'AI 分析 CASE-2' })).toBeDisabled()
  })
})
