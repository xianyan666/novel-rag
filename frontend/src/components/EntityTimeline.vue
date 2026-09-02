<script setup lang="ts">
import { ref, computed } from 'vue'
import type { EntityTimelineEvent } from '../types/api'
import EvidenceBadge from './EvidenceBadge.vue'

const props = defineProps<{
  events: EntityTimelineEvent[]
}>()

const showLowConfidence = ref(false)

const highConfidenceEvents = computed(() =>
  props.events.filter(e => (e.confidence ?? 0) >= 0.65)
)

const lowConfidenceEvents = computed(() =>
  props.events.filter(e => (e.confidence ?? 0) < 0.65)
)

const displayedEvents = computed(() =>
  showLowConfidence.value ? props.events : highConfidenceEvents.value
)

const eventTypeLabels: Record<string, string> = {
  first_seen: '首次出现',
  character_intro: '人物登场',
  character_interaction: '人物互动',
  item_obtained: '获得物品',
  item_upgrade: '物品强化',
  item_repair: '物品修复',
  item_evolution: '物品进化',
  skill_obtained: '获得技能',
  skill_upgrade: '技能升级',
  skill_awakened: '技能觉醒',
  relation_changed: '关系变化',
  faction_joined: '加入势力',
  faction_left: '离开势力',
  status_changed: '状态变化',
  major_entity_event: '重要事件',
}
</script>

<template>
  <div class="entity-timeline" v-if="events.length">
    <div class="timeline-controls" v-if="lowConfidenceEvents.length">
      <button class="btn btn-secondary" style="font-size: 11px; padding: 2px 8px;" @click="showLowConfidence = !showLowConfidence">
        {{ showLowConfidence ? '隐藏低置信候选' : `显示低置信候选 (${lowConfidenceEvents.length})` }}
      </button>
    </div>
    <div class="timeline-line">
      <div
        v-for="evt in displayedEvents"
        :key="evt.entity_event_id"
        class="timeline-node"
        :class="{ 'low-confidence': (evt.confidence ?? 0) < 0.65 }"
      >
        <div class="node-dot"></div>
        <div class="node-content">
          <div class="node-header">
            <EvidenceBadge :type="evt.event_type" :label="eventTypeLabels[evt.event_type] || evt.event_type" />
            <span class="node-chapter">第{{ evt.chapter_no }}章 {{ evt.chapter_title }}</span>
            <span class="node-confidence" v-if="evt.confidence">置信度: {{ evt.confidence.toFixed(2) }}</span>
          </div>
          <div class="node-summary" v-if="evt.summary">{{ evt.summary }}</div>
          <div class="node-evidence" v-if="evt.evidence">{{ evt.evidence }}</div>
          <div class="node-related" v-if="evt.related_entities?.length">
            相关: {{ evt.related_entities.join(', ') }}
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="empty-hint">暂无时间线数据</div>
</template>

<style scoped>
.entity-timeline {
  padding-left: 16px;
}

.timeline-line {
  border-left: 2px solid var(--line);
  padding-left: 20px;
}

.timeline-node {
  position: relative;
  margin-bottom: 16px;
}

.node-dot {
  position: absolute;
  left: -25px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.node-chapter {
  font-size: 12px;
  color: var(--muted);
}

.node-confidence {
  font-size: 11px;
  color: var(--muted);
  opacity: 0.7;
}

.node-summary {
  font-size: 13px;
  margin-top: 4px;
}

.node-evidence {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  padding: 6px 8px;
  background: var(--surface);
  border-radius: 6px;
  max-height: 60px;
  overflow: hidden;
}

.node-related {
  font-size: 11px;
  color: var(--accent-blue);
  margin-top: 4px;
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}

.timeline-controls {
  margin-bottom: 12px;
}

.timeline-node.low-confidence {
  opacity: 0.7;
}

.timeline-node.low-confidence .node-dot {
  background: var(--warning);
}
</style>
