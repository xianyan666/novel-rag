<script setup lang="ts">
import type { EntityMention } from '../types/api'

defineProps<{
  mentions: EntityMention[]
}>()
</script>

<template>
  <div class="entity-mentions" v-if="mentions.length">
    <div
      v-for="m in mentions"
      :key="m.mention_id"
      class="mention-item"
    >
      <div class="mention-meta">
        第{{ m.chapter_no }}章 {{ m.chapter_title }}
        <span class="mention-confidence" v-if="m.confidence">置信度: {{ m.confidence.toFixed(2) }}</span>
      </div>
      <div class="mention-evidence" v-if="m.evidence">{{ m.evidence }}</div>
    </div>
  </div>
  <div v-else class="empty-hint">暂无提及数据</div>
</template>

<style scoped>
.entity-mentions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mention-item {
  padding: 10px 12px;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--line);
}

.mention-meta {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mention-confidence {
  font-size: 11px;
  opacity: 0.7;
}

.mention-evidence {
  font-size: 13px;
  line-height: 1.6;
  max-height: 60px;
  overflow: hidden;
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}
</style>
