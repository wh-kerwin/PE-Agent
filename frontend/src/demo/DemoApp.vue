<script setup lang="ts">
import { ref } from 'vue'
import CaseAnalysisAction from '@/components/CaseAnalysisAction.vue'
import CaseAnalysisDrawer from '@/components/CaseAnalysisDrawer.vue'
import { createCaseAnalysisClient } from '@/api/client'
import type { CaseAnalysisCase, CaseAnalysisHost } from '@/types'
import { DEMO_CASE_ID, DEMO_CASE_VERSION } from './fixtures'
import { useCaseAnalysisStore } from '@/store/caseAnalysis'

const cases = ref<CaseAnalysisCase[]>([
  { caseId: DEMO_CASE_ID, caseVersion: DEMO_CASE_VERSION, caseType: 'YIELD_DROP', severity: 'HIGH', analysisSummary: null },
  { caseId: 'CASE-20260920-002', caseVersion: '8', caseType: 'YIELD_DROP', severity: 'CRITICAL', analysisSummary: { taskId: 'ANA-PARTIAL-002', status: 'PARTIAL_RESULT', reviewStatus: 'NOT_REVIEWED' } },
  { caseId: 'CASE-20260919-014', caseVersion: '3', caseType: 'EQUIPMENT_ALARM', severity: 'MEDIUM', analysisSummary: { supported: false, disabledReason: 'V1 仅支持 Yield Drop Case' } },
])
const client = createCaseAnalysisClient()
const host: CaseAnalysisHost = {
  onAuthRequired: () => { window.dispatchEvent(new CustomEvent('host:auth-required')) },
  onAccessDenied: (caseId) => { window.dispatchEvent(new CustomEvent('host:case-access-denied', { detail: { caseId } })) },
  onCaseVersionConflict: (caseId) => { window.dispatchEvent(new CustomEvent('host:refresh-case', { detail: { caseId } })) },
  openSource: (rawRef) => { window.dispatchEvent(new CustomEvent('host:open-source', { detail: { rawRef } })) },
}
const store = useCaseAnalysisStore()

function open(row: CaseAnalysisCase, startNew: boolean) {
  void store.openCaseAnalysis(row, startNew)
}
</script>

<template>
  <div class="demo-shell">
    <header class="topbar"><div class="brand-mark">PE</div><div><strong>Process Engineering</strong><span>Case Operations</span></div></header>
    <main class="workspace">
      <div class="page-heading"><div><p>CASE MANAGEMENT</p><h1>异常 Case</h1><span>需要工程师关注的制造异常与调查状态</span></div><a-button type="primary">新建 Case</a-button></div>
      <div class="stat-strip"><div><span>开放 Case</span><strong>12</strong></div><div><span>高优先级</span><strong>4</strong></div><div><span>AI 分析中</span><strong>2</strong></div></div>
      <section class="case-table-card" aria-labelledby="case-table-title">
        <div class="table-tools"><h2 id="case-table-title">Case Table</h2><a-input-search placeholder="搜索 Case ID" style="width: 240px" /></div>
        <a-table :data="cases" :pagination="false" row-key="caseId" :scroll="{ x: 760 }">
          <template #columns>
            <a-table-column title="Case ID" data-index="caseId"><template #cell="{ record }"><strong>{{ record.caseId }}</strong></template></a-table-column>
            <a-table-column title="类型" data-index="caseType" />
            <a-table-column title="严重度" data-index="severity"><template #cell="{ record }"><a-tag :color="record.severity === 'CRITICAL' ? 'red' : record.severity === 'HIGH' ? 'orange' : 'blue'">{{ record.severity }}</a-tag></template></a-table-column>
            <a-table-column title="数据版本" data-index="caseVersion"><template #cell="{ record }">v{{ record.caseVersion }}</template></a-table-column>
            <a-table-column title="状态"><template #cell><a-badge status="processing" text="OPEN" /></template></a-table-column>
            <a-table-column title="操作" :width="130" fixed="right"><template #cell="{ record }"><CaseAnalysisAction v-bind="record" @open="open(record, $event.startNew)" /></template></a-table-column>
          </template>
        </a-table>
      </section>
    </main>
    <CaseAnalysisDrawer :client="client" :host="host" />
  </div>
</template>

<style scoped>
.demo-shell { min-height: 100vh; background: #f3f6f8; color: #17243b; }.topbar { display: flex; align-items: center; height: 64px; padding: 0 max(24px, calc((100vw - 1180px) / 2)); gap: 11px; color: white; background: #13213a; }.brand-mark { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 8px; background: #27a6cf; font-weight: 800; }.topbar div:last-child { display: grid; }.topbar span { color: #aebbd0; font-size: 11px; }.workspace { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0; }.page-heading { display: flex; justify-content: space-between; align-items: end; }.page-heading p { margin: 0 0 5px; color: #147da4; font-size: 11px; font-weight: 700; letter-spacing: .13em; }.page-heading h1 { margin: 0; font-size: 30px; }.page-heading span { display: block; margin-top: 6px; color: #6c7889; }.stat-strip { display: grid; grid-template-columns: repeat(3, 1fr); margin: 25px 0; gap: 12px; }.stat-strip div { padding: 16px 18px; border: 1px solid #e1e7ec; border-radius: 10px; background: white; }.stat-strip span { color: #718096; font-size: 12px; }.stat-strip strong { display: block; margin-top: 4px; font-size: 23px; }.case-table-card { overflow: hidden; border: 1px solid #e1e7ec; border-radius: 12px; background: white; box-shadow: 0 8px 30px rgba(30,55,75,.05); }.table-tools { display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; border-bottom: 1px solid #edf0f3; }.table-tools h2 { margin: 0; font-size: 17px; }
@media (max-width: 650px) { .workspace { width: calc(100% - 20px); padding-top: 20px; }.page-heading { align-items: flex-start; gap: 14px; }.stat-strip { grid-template-columns: 1fr; }.table-tools { align-items: stretch; flex-direction: column; gap: 12px; } }
</style>
