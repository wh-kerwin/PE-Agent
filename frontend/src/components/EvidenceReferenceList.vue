<script setup lang="ts">
import { computed } from 'vue'
import { IconLink } from '@arco-design/web-vue/es/icon'
import type { Evidence } from '@/types'

const props = defineProps<{
  evidenceIds: string[]
  evidence: Evidence[]
}>()

const emit = defineEmits<{ openSource: [rawRef: string] }>()

const items = computed(() => {
  const byId = new Map(props.evidence.map((item) => [item.evidenceId, item]))
  return props.evidenceIds.map((id) => byId.get(id)).filter((item): item is Evidence => !!item)
})

const qualityLabels: Record<Evidence['quality'], string> = {
  VERIFIED: '已验证', PARTIAL: '部分可用', CONFLICTING: '存在冲突',
}
</script>

<template>
  <div class="evidence-list">
    <a-collapse :bordered="false">
      <a-collapse-item v-for="item in items" :key="item.evidenceId" :header="item.observation" :name="item.evidenceId">
        <dl class="evidence-meta">
          <div><dt>来源</dt><dd>{{ item.source.system }} · {{ item.source.sourceId }}</dd></div>
          <div><dt>事件时间</dt><dd>{{ new Date(item.eventTime).toLocaleString() }}</dd></div>
          <div><dt>读取时间</dt><dd>{{ new Date(item.retrievedAt).toLocaleString() }}</dd></div>
          <div v-if="item.unit"><dt>单位</dt><dd>{{ item.unit }}</dd></div>
          <div><dt>数据质量</dt><dd>{{ qualityLabels[item.quality] }}</dd></div>
          <div><dt>关联实体</dt><dd>{{ item.entityRefs.map((ref) => `${ref.type}: ${ref.id}`).join('，') }}</dd></div>
        </dl>
        <a-button type="text" size="small" :aria-label="`查看原始数据 ${item.evidenceId}`" @click.stop="emit('openSource', item.rawRef)">
          <template #icon><IconLink /></template>
          查看原始数据
        </a-button>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<style scoped>
.evidence-list { margin-top: 10px; border: 1px solid var(--color-neutral-3); border-radius: 8px; overflow: hidden; }
.evidence-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0 0 8px; gap: 8px 20px; }
.evidence-meta div { min-width: 0; }
dt { color: var(--color-text-3); font-size: 12px; }
dd { margin: 2px 0 0; overflow-wrap: anywhere; }
@media (max-width: 600px) { .evidence-meta { grid-template-columns: 1fr; } }
</style>
