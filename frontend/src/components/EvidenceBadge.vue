<script setup lang="ts">
defineProps<{
  type: string
  label?: string
}>()

const typeColors: Record<string, string> = {
  character: 'var(--accent-blue)',
  item: 'var(--accent)',
  skill: '#8b5cf6',
  faction: 'var(--success)',
  place: '#06b6d4',
  world: '#06b6d4',
  concept: '#697586',
  title: '#d88a00',
  candidate: 'var(--warning)',
  active: 'var(--success)',
  protected: '#20a162',
  supplemental: '#697586',
  low_confidence: '#d88a00',
  entity_weighted: 'var(--accent-blue)',
}
</script>

<template>
  <span class="evidence-badge" :style="{ background: typeColors[type] || '#697586' }">
    {{ label || type }}
  </span>
</template>

<style scoped>
.evidence-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: white;
  white-space: nowrap;
}
</style>
