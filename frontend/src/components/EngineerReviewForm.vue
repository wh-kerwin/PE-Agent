<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { EngineerReview, EngineerReviewInput, Hypothesis, ReviewStatus } from '@/types'

const props = defineProps<{
  reportVersion: number
  hypotheses: Hypothesis[]
  savedReview?: EngineerReview | null
  pending?: boolean
}>()

const emit = defineEmits<{
  submit: [input: Omit<EngineerReviewInput, 'reportVersion' | 'idempotencyKey'>]
  dirtyChange: [dirty: boolean]
}>()

const form = reactive({
  helpful: 'unset' as 'yes' | 'no' | 'unset',
  reviewStatus: '' as Exclude<ReviewStatus, 'NOT_REVIEWED'> | '',
  confirmedHypothesisId: '' as string,
  actualRootCause: '',
  comment: '',
})
const errors = ref<string[]>([])
const dirty = ref(false)
let hydrating = false
const statuses = [
  { value: 'CONFIRMED', label: '确认分析结论' },
  { value: 'CORRECTED', label: '修正分析结论' },
  { value: 'INCONCLUSIVE', label: '证据不足' },
] as const

watch(form, () => {
  if (hydrating) return
  dirty.value = true
  emit('dirtyChange', true)
}, { deep: true, flush: 'sync' })
function resetForm() {
  hydrating = true
  form.helpful = 'unset'
  form.reviewStatus = ''
  form.confirmedHypothesisId = ''
  form.actualRootCause = ''
  form.comment = ''
  dirty.value = false
  errors.value = []
  hydrating = false
  emit('dirtyChange', false)
}
function hydrateReview(review: EngineerReview | null | undefined) {
  hydrating = true
  if (!review) {
    resetForm()
    return
  }
  form.helpful = review.helpful === null ? 'unset' : review.helpful ? 'yes' : 'no'
  form.reviewStatus = review.reviewStatus
  form.confirmedHypothesisId = review.confirmedHypothesisId ?? ''
  form.actualRootCause = review.actualRootCause ?? ''
  form.comment = review.comment ?? ''
  dirty.value = false
  errors.value = []
  hydrating = false
  emit('dirtyChange', false)
}
watch(() => props.savedReview, (review) => hydrateReview(review), { immediate: true })
watch(() => props.reportVersion, () => hydrateReview(props.savedReview))

const needsCause = computed(() => form.reviewStatus === 'CORRECTED')
const needsHypothesis = computed(() => form.reviewStatus === 'CONFIRMED')

function submit() {
  errors.value = []
  if (!form.reviewStatus) errors.value.push('请选择工程结论。')
  if (needsHypothesis.value && !form.confirmedHypothesisId) errors.value.push('确认分析结论时请选择已确认假设。')
  if (needsCause.value && !form.actualRootCause.trim()) errors.value.push('修正结论时请填写实际根因。')
  if (errors.value.length || !form.reviewStatus) return
  emit('submit', {
    reviewStatus: form.reviewStatus,
    helpful: form.helpful === 'unset' ? null : form.helpful === 'yes',
    confirmedHypothesisId: form.reviewStatus === 'CONFIRMED' ? form.confirmedHypothesisId || null : null,
    actualRootCause: form.reviewStatus === 'CORRECTED' ? form.actualRootCause.trim() || null : null,
    comment: form.comment.trim() || null,
  })
}
</script>

<template>
  <section class="report-section review-section" aria-labelledby="review-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">ENGINEER REVIEW</p>
        <h2 id="review-title">工程师复核</h2>
      </div>
      <a-tag v-if="savedReview" color="green">已保存 · Revision {{ savedReview.reviewRevision }}</a-tag>
    </div>

    <div class="field-group">
      <span class="field-label">这份分析是否有帮助？（可选）</span>
      <a-radio-group v-model="form.helpful" type="button">
        <a-radio value="yes">有帮助</a-radio>
        <a-radio value="no">没有帮助</a-radio>
        <a-radio value="unset">暂不评价</a-radio>
      </a-radio-group>
    </div>

    <div class="field-group">
      <span class="field-label">工程结论 <span aria-hidden="true">*</span></span>
      <a-radio-group v-model="form.reviewStatus" direction="vertical">
        <a-radio v-for="status in statuses" :key="status.value" :value="status.value">{{ status.label }}</a-radio>
      </a-radio-group>
    </div>

    <label v-if="form.reviewStatus === 'CONFIRMED'" class="field-group">
      <span class="field-label">确认的假设 <span aria-hidden="true">*</span></span>
      <a-select v-model="form.confirmedHypothesisId" allow-clear placeholder="选择已确认假设">
        <a-option v-for="hypothesis in hypotheses" :key="hypothesis.hypothesisId" :value="hypothesis.hypothesisId">
          {{ hypothesis.title }}
        </a-option>
      </a-select>
    </label>

    <label v-if="needsCause" class="field-group">
      <span class="field-label">实际根因</span>
      <a-textarea v-model="form.actualRootCause" :max-length="1000" show-word-limit placeholder="填写工程验证后的实际根因" />
    </label>

    <label class="field-group">
      <span class="field-label">复核说明（可选）</span>
      <a-textarea v-model="form.comment" :max-length="2000" show-word-limit placeholder="记录验证过程或后续建议" />
    </label>

    <a-alert v-if="errors.length" type="error" role="alert">
      <ul><li v-for="message in errors" :key="message">{{ message }}</li></ul>
    </a-alert>
    <a-button type="primary" :loading="pending" :disabled="!dirty" @click="submit">保存复核</a-button>
  </section>
</template>

<style scoped>
.review-section { display: grid; gap: 18px; }
.field-group { display: grid; gap: 8px; }
.field-label { color: var(--color-text-2); font-weight: 600; }
ul { margin: 0; padding-left: 20px; }
</style>
