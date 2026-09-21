<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { IconCheckCircle, IconClose, IconExclamationCircle, IconLoading, IconRefresh } from '@arco-design/web-vue/es/icon'
import { useCaseAnalysisStore } from '@/store/caseAnalysis'
import type { CaseAnalysisClient, CaseAnalysisHost, Evidence, Finding, Recommendation } from '@/types'
import { isTerminalStatus } from '@/types'
import EngineerReviewForm from './EngineerReviewForm.vue'
import EvidenceReferenceList from './EvidenceReferenceList.vue'

const props = defineProps<{
  client: CaseAnalysisClient
  host: CaseAnalysisHost
}>()
const emit = defineEmits<{ closed: [] }>()
const store = useCaseAnalysisStore()
store.configure(props.client, props.host)
const {
  drawerOpen, activeCase, activeTask, activeReport, activeReview, activeArchive,
  connectionStatus, loading, actionPending, reviewPending, archivePending, error,
} = storeToRefs(store)
const drawerPanel = ref<HTMLElement | null>(null)
const reviewDirty = ref(false)
const closePromptOpen = ref(false)
const mobile = ref(false)

const statusLabels: Record<string, string> = {
  CREATED: '已创建', CONTEXT_LOADING: '加载上下文', INVESTIGATING: '调查中', ANALYZING: '分析中',
  GENERATING_REPORT: '生成报告', COMPLETED: '分析完成', PARTIAL_RESULT: '部分结果', FAILED: '分析失败',
  TIMEOUT: '分析超时', CANCELLED: '已取消',
}
const phaseLabels: Record<string, string> = {
  CREATED: '准备分析', CONTEXT_LOADING: '读取 Case 上下文', INVESTIGATING: '调查证据',
  ANALYZING: '分析关联', GENERATING_REPORT: '生成分析报告',
}
const canRetry = computed(() => !!activeTask.value && ['FAILED', 'TIMEOUT', 'PARTIAL_RESULT'].includes(activeTask.value.status))
const running = computed(() => !!activeTask.value && !isTerminalStatus(activeTask.value.status))
const progress = computed(() => Math.max(0, Math.min(100, activeTask.value?.progress ?? 0)))
const warnings = computed(() => (activeTask.value?.warnings ?? []).map((warning) => typeof warning === 'string' ? warning : warning.message))
const evidenceById = computed(() => new Map((activeReport.value?.evidence ?? []).map((item) => [item.evidenceId, item])))

watch(drawerOpen, async (open) => {
  if (open) {
    await nextTick()
    drawerPanel.value?.focus()
  }
})
watch(() => [props.client, props.host] as const, ([client, host]) => store.configure(client, host))

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  document.addEventListener('visibilitychange', store.onVisibilityChange)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
  document.removeEventListener('visibilitychange', store.onVisibilityChange)
})

function updateViewport() { mobile.value = window.innerWidth < 720 }
function requestClose() {
  if (reviewDirty.value) closePromptOpen.value = true
  else close()
}
function close() {
  closePromptOpen.value = false
  reviewDirty.value = false
  store.closeDrawer()
  emit('closed')
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    requestClose()
  }
}
function source(rawRef: string) { void props.host.openSource(rawRef) }
function linkedEvidence(ids: string[]): Evidence[] {
  return ids.map((id) => evidenceById.value.get(id)).filter((item): item is Evidence => !!item)
}
function warningText(value: unknown) { return typeof value === 'string' ? value : '部分数据源不可用' }
</script>

<template>
  <a-drawer
    :visible="drawerOpen"
    :width="mobile ? '100%' : 820"
    :mask-closable="false"
    :esc-to-close="false"
    :footer="false"
    :unmount-on-close="false"
    placement="right"
    @cancel="requestClose"
  >
    <template #title>
      <div class="drawer-title">
        <span>Case AI 分析</span>
        <a-tag v-if="activeTask" :color="activeTask.status === 'PARTIAL_RESULT' ? 'orange' : activeTask.status === 'COMPLETED' ? 'green' : 'blue'">
          {{ statusLabels[activeTask.status] ?? activeTask.status }}
        </a-tag>
      </div>
    </template>
    <template #close-icon><IconClose aria-label="关闭分析" /></template>

    <main ref="drawerPanel" class="analysis-drawer" tabindex="-1" @keydown="onKeydown">
      <header class="case-header">
        <div>
          <p class="eyebrow">CASE</p>
          <h1>{{ activeCase?.caseId ?? '加载中' }}</h1>
        </div>
        <dl class="case-meta">
          <div><dt>类型</dt><dd>{{ activeCase?.caseType ?? activeReport?.caseSnapshot.caseType ?? '—' }}</dd></div>
          <div><dt>严重度</dt><dd>{{ activeCase?.severity ?? activeReport?.summary.severity ?? '—' }}</dd></div>
          <div><dt>数据版本</dt><dd>v{{ activeCase?.caseVersion ?? '—' }}</dd></div>
          <div><dt>任务</dt><dd>{{ activeTask?.taskId ?? '—' }}</dd></div>
        </dl>
      </header>

      <div class="live-region" aria-live="polite" aria-atomic="true">
        <span v-if="connectionStatus === 'recovering'">实时连接中断，正在恢复连接。分析任务仍在后台运行。</span>
        <span v-else-if="running">{{ phaseLabels[activeTask?.phase ?? ''] ?? activeTask?.phase ?? '正在分析' }}，{{ progress }}%</span>
      </div>

      <section v-if="loading" class="stable-skeleton" aria-label="正在加载分析">
        <a-skeleton :animation="true"><a-skeleton-line :rows="8" /></a-skeleton>
      </section>

      <template v-else>
        <a-alert v-if="error" type="error" show-icon role="alert">
          <template #title>无法加载分析</template>{{ error }}
          <template #action><a-button size="small" @click="store.createOrResume">重试</a-button></template>
        </a-alert>

        <section v-if="activeTask && running" class="progress-panel" aria-labelledby="progress-title">
          <div class="section-heading compact">
            <div><p class="eyebrow">LIVE INVESTIGATION</p><h2 id="progress-title">{{ phaseLabels[activeTask.phase ?? ''] ?? activeTask.phase ?? '正在分析' }}</h2></div>
            <span class="progress-number">{{ progress }}%</span>
          </div>
          <a-progress :percent="progress / 100" :show-text="false" status="normal" />
          <div v-if="connectionStatus === 'recovering'" class="connection-note"><IconRefresh /> 正在恢复连接，不影响后台任务</div>
          <ol v-if="activeTask.events?.length" class="event-list">
            <li v-for="event in activeTask.events" :key="event.sequence">
              <IconExclamationCircle v-if="event.state === 'failed'" class="event-failed" />
              <IconCheckCircle v-else-if="event.state === 'completed'" class="event-complete" />
              <IconLoading v-else spin />
              <span>{{ event.message }}</span>
              <time>{{ new Date(event.occurredAt).toLocaleTimeString() }}</time>
            </li>
          </ol>
          <a-button size="small" :loading="actionPending" @click="store.cancelTask">取消分析</a-button>
        </section>

        <a-alert v-if="activeTask?.status === 'PARTIAL_RESULT'" type="warning" show-icon class="partial-alert">
          <template #title>部分结果：可用内容已保留</template>
          <p>部分数据源未能完成读取，请结合以下缺口复核报告。</p>
          <ul v-if="warnings.length"><li v-for="item in warnings" :key="item">{{ warningText(item) }}</li></ul>
        </a-alert>

        <section v-if="warnings.length && activeTask?.status !== 'PARTIAL_RESULT'" class="data-gap" aria-labelledby="gap-title">
          <p class="eyebrow">DATA GAPS</p><h2 id="gap-title">数据缺口</h2>
          <ul><li v-for="item in warnings" :key="item">{{ item }}</li></ul>
        </section>

        <template v-if="activeReport">
          <section class="report-hero" aria-labelledby="summary-title">
            <p class="eyebrow">SUMMARY & IMPACT</p>
            <h2 id="summary-title">{{ activeReport.summary.title }}</h2>
            <p class="plain-text">{{ activeReport.summary.overview }}</p>
            <div class="impact-grid">
              <div><span>实际良率</span><strong>{{ activeReport.impact.yield.observedPercent }}%</strong></div>
              <div><span>基线良率</span><strong>{{ activeReport.impact.yield.baselinePercent }}%</strong></div>
              <div><span>绝对下降</span><strong>−{{ activeReport.impact.yield.absoluteDropPercentagePoints }} pp</strong></div>
              <div><span>受影响 Lot</span><strong>{{ activeReport.impact.affectedLots.length }}</strong></div>
            </div>
          </section>

          <section class="report-section" aria-labelledby="hypotheses-title">
            <div class="section-heading"><div><p class="eyebrow">HYPOTHESES</p><h2 id="hypotheses-title">AI 假设</h2></div><span class="count">{{ activeReport.hypotheses.length }}</span></div>
            <article v-for="hypothesis in activeReport.hypotheses" :key="hypothesis.hypothesisId" class="content-card hypothesis-card">
              <div class="card-title"><h3>{{ hypothesis.title }}</h3><a-tag color="arcoblue">AI 假设 · {{ hypothesis.confidenceLevel }}</a-tag></div>
              <div class="hypothesis-columns">
                <div><h4>支持证据</h4><EvidenceReferenceList :evidence-ids="hypothesis.supportingEvidenceIds" :evidence="activeReport.evidence" @open-source="source" /></div>
                <div><h4>反证</h4><p v-if="!hypothesis.contradictingEvidenceIds.length" class="empty-copy">暂无反证</p><EvidenceReferenceList v-else :evidence-ids="hypothesis.contradictingEvidenceIds" :evidence="activeReport.evidence" @open-source="source" /></div>
              </div>
              <div class="missing-evidence"><h4>缺失证据</h4><ul><li v-for="gap in hypothesis.missingEvidence" :key="gap">{{ gap }}</li><li v-if="!hypothesis.missingEvidence.length">未识别到额外缺口</li></ul></div>
              <details class="model-signal"><summary>查看模型判断信号</summary><p>原始回答：{{ hypothesis.modelAssessment.answer }} · 模型：{{ hypothesis.modelAssessment.resolvedModel }}</p></details>
            </article>
          </section>

          <section class="report-section" aria-labelledby="findings-title">
            <div class="section-heading"><div><p class="eyebrow">FINDINGS & EVIDENCE</p><h2 id="findings-title">发现与证据</h2></div><span class="count">{{ activeReport.findings.length }}</span></div>
            <article v-for="finding in activeReport.findings" :key="finding.findingId" class="content-card">
              <div class="card-title"><h3>{{ finding.title }}</h3><a-tag>{{ finding.level === 'OBSERVED' ? '已观察' : '推断' }}</a-tag></div>
              <p class="plain-text">{{ finding.description }}</p>
              <EvidenceReferenceList :evidence-ids="finding.evidenceIds" :evidence="activeReport.evidence" @open-source="source" />
            </article>
          </section>

          <section v-if="activeReport.correlations.length" class="report-section" aria-labelledby="correlations-title">
            <p class="eyebrow">CORRELATIONS</p><h2 id="correlations-title">关联线索</h2>
            <article v-for="item in activeReport.correlations" :key="item.correlationId" class="compact-row">
              <a-tag>{{ item.type }}</a-tag><p class="plain-text">{{ item.description }}</p>
            </article>
          </section>

          <section class="report-section" aria-labelledby="timeline-title">
            <p class="eyebrow">TIMELINE</p><h2 id="timeline-title">时间线</h2>
            <a-timeline>
              <a-timeline-item v-for="item in activeReport.timeline" :key="item.eventId" :label="new Date(item.occurredAt).toLocaleString()">
                <strong>{{ item.title }}</strong>
                <EvidenceReferenceList :evidence-ids="item.evidenceIds" :evidence="activeReport.evidence" @open-source="source" />
              </a-timeline-item>
            </a-timeline>
          </section>

          <section v-if="activeReport.similarCases.length" class="report-section" aria-labelledby="similar-title">
            <p class="eyebrow">SIMILAR CASES</p><h2 id="similar-title">相似 Case</h2>
            <article v-for="item in activeReport.similarCases" :key="item.caseId" class="content-card">
              <h3>{{ item.caseId }}</h3><p class="plain-text">{{ item.similarityReason }}</p>
              <EvidenceReferenceList :evidence-ids="[item.evidenceId]" :evidence="activeReport.evidence" @open-source="source" />
            </article>
          </section>

          <section class="report-section" aria-labelledby="recommendations-title">
            <p class="eyebrow">RECOMMENDATIONS</p><h2 id="recommendations-title">建议</h2>
            <article v-for="item in activeReport.recommendations" :key="item.recommendationId" class="content-card recommendation">
              <a-tag color="purple">{{ item.category }}</a-tag><h3>{{ item.action }}</h3><p class="plain-text">{{ item.reason }}</p>
              <EvidenceReferenceList :evidence-ids="item.evidenceIds" :evidence="activeReport.evidence" @open-source="source" />
            </article>
          </section>

          <section v-if="activeReport.uncertainties.length" class="report-section uncertainty" aria-labelledby="uncertainty-title">
            <p class="eyebrow">UNCERTAINTIES</p><h2 id="uncertainty-title">尚未确认</h2>
            <article v-for="item in activeReport.uncertainties" :key="item.uncertaintyId"><strong>{{ item.description }}</strong><p>{{ item.impact }}</p></article>
          </section>

          <EngineerReviewForm
            :report-version="activeReport.reportVersion"
            :hypotheses="activeReport.hypotheses"
            :saved-review="activeReview"
            :pending="reviewPending"
            @dirty-change="reviewDirty = $event"
            @submit="store.submitReview"
          />

          <section v-if="activeReview" class="archive-panel" aria-labelledby="archive-title">
            <div><p class="eyebrow">CASE BOOK</p><h2 id="archive-title">归档复核结果</h2><p>保存 AI 报告版本与工程师结论，不修改原始报告。</p></div>
            <a-result v-if="activeArchive?.status === 'ARCHIVED'" status="success" title="已归档 Case Book" :subtitle="activeArchive.archiveId" />
            <a-alert v-else-if="activeArchive?.status === 'FAILED'" type="error">归档失败，可安全重试。</a-alert>
            <a-button v-if="activeArchive?.status !== 'ARCHIVED'" type="primary" :loading="archivePending" @click="store.archiveCaseBook">保存到 Case Book</a-button>
          </section>
        </template>

        <section v-else-if="activeTask && isTerminalStatus(activeTask.status)" class="empty-result">
          <a-result status="error" :title="statusLabels[activeTask.status] ?? activeTask.status" subtitle="未生成可用报告。">
            <template #extra><a-button v-if="canRetry" type="primary" :loading="actionPending" @click="store.retryAsNewTask">重新分析</a-button></template>
          </a-result>
        </section>
      </template>
    </main>
  </a-drawer>

  <a-modal v-model:visible="closePromptOpen" title="放弃未保存的复核？" :mask-closable="false" @ok="close">
    <p>复核表单尚未保存。关闭后，本次填写内容将丢失；后台分析任务不会取消。</p>
  </a-modal>
</template>

<style scoped>
.analysis-drawer { max-width: 100%; min-height: 620px; padding-bottom: 40px; outline: none; color: var(--color-text-1); }
.drawer-title, .section-heading, .card-title { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.case-header { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(360px, 1.6fr); gap: 28px; padding: 8px 0 24px; border-bottom: 1px solid var(--color-neutral-3); }
h1, h2, h3, h4, p { margin-top: 0; } h1 { margin-bottom: 0; font-size: 27px; } h2 { margin-bottom: 12px; font-size: 20px; } h3 { margin-bottom: 8px; font-size: 16px; } h4 { margin-bottom: 6px; }
.eyebrow { margin-bottom: 5px; color: rgb(var(--primary-6)); font-size: 11px; font-weight: 700; letter-spacing: .12em; }
.case-meta { display: grid; grid-template-columns: repeat(2, 1fr); margin: 0; gap: 12px 18px; }.case-meta div { min-width: 0; }.case-meta dt { color: var(--color-text-3); font-size: 12px; }.case-meta dd { margin: 3px 0 0; font-weight: 600; overflow-wrap: anywhere; }
.live-region { min-height: 22px; padding: 7px 0; color: var(--color-text-3); font-size: 12px; }
.stable-skeleton { min-height: 560px; padding-top: 24px; }
.progress-panel, .report-hero, .report-section, .data-gap, .archive-panel { margin-top: 18px; padding: 22px; border: 1px solid var(--color-neutral-3); border-radius: 12px; background: var(--color-bg-2); }
.progress-panel { background: linear-gradient(145deg, rgb(var(--primary-1)), var(--color-bg-2) 62%); }.section-heading.compact h2 { margin-bottom: 0; }.progress-number { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }.connection-note { display: flex; gap: 6px; align-items: center; margin-top: 10px; color: rgb(var(--orange-6)); }
.event-list { display: grid; margin: 18px 0; padding: 0; gap: 10px; list-style: none; }.event-list li { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 8px; }.event-list time { color: var(--color-text-3); font-size: 12px; }.event-complete { color: rgb(var(--green-6)); }.event-failed { color: rgb(var(--orange-6)); }
.partial-alert { margin-top: 18px; }.partial-alert p { margin-bottom: 5px; }.partial-alert ul, .data-gap ul, .missing-evidence ul { margin-bottom: 0; padding-left: 20px; }
.report-hero { color: white; border: 0; background: linear-gradient(135deg, #16233d 0%, #234d74 100%); }.report-hero .eyebrow { color: #8dd8ff; }.report-hero .plain-text { max-width: 68ch; color: rgba(255,255,255,.87); line-height: 1.7; }
.impact-grid { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 20px; gap: 10px; }.impact-grid div { padding: 12px; border: 1px solid rgba(255,255,255,.16); border-radius: 8px; background: rgba(255,255,255,.07); }.impact-grid span { display: block; color: rgba(255,255,255,.67); font-size: 12px; }.impact-grid strong { display: block; margin-top: 4px; font-size: 20px; }
.count { display: grid; place-items: center; min-width: 28px; height: 28px; border-radius: 50%; background: var(--color-neutral-2); font-weight: 700; }.content-card { margin-top: 12px; padding: 18px; border: 1px solid var(--color-neutral-3); border-radius: 9px; background: var(--color-fill-1); }.plain-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.65; }.hypothesis-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }.empty-copy { color: var(--color-text-3); }.missing-evidence { margin-top: 15px; padding: 12px; border-left: 3px solid rgb(var(--orange-5)); background: rgb(var(--orange-1)); }.model-signal { margin-top: 12px; color: var(--color-text-3); }.model-signal summary { cursor: pointer; }.model-signal p { margin: 8px 0 0; }
.compact-row { display: flex; align-items: start; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--color-neutral-3); }.compact-row:last-child { border-bottom: 0; }.compact-row p { margin: 0; }.recommendation > h3 { margin-top: 10px; }.uncertainty { border-color: rgb(var(--orange-3)); }.uncertainty article + article { margin-top: 14px; }.uncertainty article p { margin: 4px 0 0; color: var(--color-text-2); }
.archive-panel { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 20px; }.archive-panel p:last-child { margin-bottom: 0; color: var(--color-text-3); }.empty-result { min-height: 400px; display: grid; place-items: center; }
@media (max-width: 719px) { .analysis-drawer { min-height: calc(100vh - 90px); }.case-header { grid-template-columns: 1fr; gap: 18px; }.impact-grid { grid-template-columns: repeat(2, 1fr); }.hypothesis-columns { grid-template-columns: 1fr; }.archive-panel { grid-template-columns: 1fr; }.progress-panel, .report-hero, .report-section, .data-gap, .archive-panel { padding: 16px; border-radius: 9px; }.event-list li { grid-template-columns: 18px minmax(0, 1fr); }.event-list time { grid-column: 2; } }
@media (max-width: 420px) { .case-meta, .impact-grid { grid-template-columns: 1fr; }.card-title { align-items: flex-start; flex-direction: column; } }
</style>
