<script setup lang="ts">
import type { EntityRelation } from '../types/api'
import EvidenceBadge from './EvidenceBadge.vue'

defineProps<{
  relations: EntityRelation[]
  entityName?: string
}>()

const relationLabels: Record<string, string> = {
  owns: '持有',
  uses: '使用',
  upgrades: '强化',
  member_of: '属于',
  ally_of: '同盟',
  enemy_of: '敌对',
  meets: '相遇',
  interacts_with: '互动',
  teacher_of: '指导',
  created_by: '创造',
  located_in: '位于',
  part_of: '从属',
  related_to: '相关',
}
</script>

<template>
  <div class="entity-relations" v-if="relations.length">
    <div
      v-for="rel in relations"
      :key="rel.relation_id"
      class="relation-item"
      :class="{ candidate: rel.status === 'candidate' }"
    >
      <div class="relation-header">
        <span class="relation-source">{{ rel.source_name }}</span>
        <EvidenceBadge :type="rel.relation_type" :label="relationLabels[rel.relation_type] || rel.relation_type" />
        <span class="relation-target">{{ rel.target_name }}</span>
        <span v-if="rel.status === 'candidate'" class="candidate-tag">候选</span>
      </div>
      <div class="relation-meta">
        第{{ rel.chapter_no }}章 {{ rel.chapter_title }}
        <span class="relation-confidence" v-if="rel.confidence">置信度: {{ rel.confidence.toFixed(2) }}</span>
      </div>
      <div class="relation-evidence" v-if="rel.evidence">{{ rel.evidence }}</div>
    </div>
  </div>
  <div v-else class="empty-hint">暂无关系数据</div>
</template>

<style scoped>
.entity-relations {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relation-item {
  padding: 10px 12px;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--line);
}

.relation-item.candidate {
  border-color: var(--warning);
  opacity: 0.85;
}

.relation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.relation-source, .relation-target {
  font-size: 13px;
  font-weight: 500;
}

.candidate-tag {
  font-size: 11px;
  color: var(--warning);
  border: 1px solid var(--warning);
  padding: 1px 6px;
  border-radius: 4px;
}

.relation-meta {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

.relation-confidence {
  margin-left: 8px;
  opacity: 0.7;
}

.relation-evidence {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  padding: 6px 8px;
  background: rgba(0,0,0,0.03);
  border-radius: 6px;
  max-height: 48px;
  overflow: hidden;
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}
</style>
