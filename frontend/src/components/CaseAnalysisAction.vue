<script setup lang="ts">
import { computed } from 'vue'
import { IconEye, IconRefresh, IconRobot } from '@arco-design/web-vue/es/icon'
import type { CaseAnalysisSummary } from '@/types'

const props = withDefaults(defineProps<{
  caseId: string
  caseVersion: string
  analysisSummary?: CaseAnalysisSummary | null
  disabled?: boolean
  disabledReason?: string
}>(), {
  analysisSummary: null,
  disabled: false,
  disabledReason: '',
})

const emit = defineEmits<{
  open: [{ caseId: string; caseVersion: string; startNew: boolean }]
}>()

const running = computed(() => props.analysisSummary?.status != null && [
  'CREATED', 'CONTEXT_LOADING', 'INVESTIGATING', 'ANALYZING', 'GENERATING_REPORT',
].includes(props.analysisSummary.status))
const hasReport = computed(() => props.analysisSummary?.status === 'COMPLETED' || props.analysisSummary?.status === 'PARTIAL_RESULT')
const unavailableReason = computed(() => props.disabledReason || props.analysisSummary?.disabledReason ||
  (props.analysisSummary?.supported === false ? 'V1 仅支持 Yield Drop Case' : ''))
const isDisabled = computed(() => props.disabled || !!unavailableReason.value)
const label = computed(() => running.value ? '分析中' : hasReport.value ? '查看分析' : props.analysisSummary?.taskId ? '重新分析' : 'AI 分析')
const tooltip = computed(() => unavailableReason.value || (running.value ? '查看实时分析进度' : label.value))

function activate() {
  if (isDisabled.value) return
  emit('open', {
    caseId: props.caseId,
    caseVersion: props.caseVersion,
    startNew: !!props.analysisSummary?.taskId && !running.value && !hasReport.value,
  })
}
</script>

<template>
  <a-tooltip :content="tooltip">
    <span class="analysis-action-wrap">
      <a-button
        class="analysis-action"
        type="text"
        size="small"
        :disabled="isDisabled"
        :loading="running"
        :aria-label="`${label} ${caseId}`"
        @click="activate"
      >
        <template #icon>
          <IconEye v-if="hasReport" />
          <IconRefresh v-else-if="analysisSummary?.taskId && !running" />
          <IconRobot v-else />
        </template>
        <span>{{ label }}</span>
      </a-button>
    </span>
  </a-tooltip>
</template>

<style scoped>
.analysis-action-wrap { display: inline-flex; width: 108px; justify-content: flex-start; }
.analysis-action { min-width: 104px; justify-content: flex-start; white-space: nowrap; }
</style>
