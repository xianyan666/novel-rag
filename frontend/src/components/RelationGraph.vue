<script setup lang="ts">
import type { EntityRelation } from '../types/api'

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
  related_to: '相关',
}
</script>

<template>
  <div class="relation-graph" v-if="relations.length">
    <div class="graph-list">
      <div
        v-for="rel in relations"
        :key="rel.relation_id"
        class="graph-edge"
      >
        <span class="edge-node">{{ rel.source_name }}</span>
        <span class="edge-arrow">&rarr;</span>
        <span class="edge-label">{{ relationLabels[rel.relation_type] || rel.relation_type }}</span>
        <span class="edge-arrow">&rarr;</span>
        <span class="edge-node">{{ rel.target_name }}</span>
        <span class="edge-chapter">第{{ rel.chapter_no }}章</span>
      </div>
    </div>
  </div>
  <div v-else class="empty-hint">暂无关系图数据</div>
</template>

<style scoped>
.relation-graph {
  padding: 8px;
}

.graph-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.graph-edge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--line);
  font-size: 13px;
}

.edge-node {
  font-weight: 500;
  color: var(--accent-blue);
}

.edge-arrow {
  color: var(--muted);
  font-size: 12px;
}

.edge-label {
  color: var(--accent);
  font-size: 12px;
  padding: 1px 6px;
  background: rgba(255, 105, 0, 0.08);
  border-radius: 4px;
}

.edge-chapter {
  margin-left: auto;
  font-size: 11px;
  color: var(--muted);
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}
</style>
