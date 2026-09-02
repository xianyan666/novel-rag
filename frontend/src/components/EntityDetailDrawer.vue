<script setup lang="ts">
import { useProjectStore } from '../stores/projectStore'
import EvidenceBadge from './EvidenceBadge.vue'
import EntityTimeline from './EntityTimeline.vue'
import EntityMentions from './EntityMentions.vue'
import EntityRelations from './EntityRelations.vue'

const store = useProjectStore()

const typeLabels: Record<string, string> = {
  character: '人物',
  item: '物品',
  skill: '技能',
  place: '地点',
  faction: '势力',
  world: '世界',
  concept: '概念',
  title: '称号',
  unknown: '未知',
}
</script>

<template>
  <div class="drawer-overlay" v-if="store.entityDrawerOpen" @click.self="store.closeEntityDrawer()">
    <div class="drawer-panel">
      <div class="drawer-header">
        <h3>实体详情</h3>
        <button class="btn-close" @click="store.closeEntityDrawer()">&times;</button>
      </div>

      <div class="drawer-body" v-if="store.selectedEntity">
        <div class="entity-card">
          <div class="entity-name">
            {{ store.selectedEntity.name }}
            <EvidenceBadge :type="store.selectedEntity.type" :label="typeLabels[store.selectedEntity.type] || store.selectedEntity.type" />
          </div>
          <div class="entity-meta">
            <div v-if="store.selectedEntity.first_seen_chapter">
              首次出现: 第{{ store.selectedEntity.first_seen_chapter }}章 {{ store.selectedEntity.first_seen_title || '' }}
            </div>
            <div v-if="store.selectedEntity.aliases?.length">
              别名: {{ store.selectedEntity.aliases.join(', ') }}
            </div>
            <div>
              置信度: {{ store.selectedEntity.confidence?.toFixed(2) || '-' }}
              <span v-if="store.selectedEntity.status === 'candidate'" class="candidate-tag">候选</span>
            </div>
          </div>
        </div>

        <div class="drawer-section">
          <h4>生命周期 ({{ store.selectedEntityTimeline.length }})</h4>
          <EntityTimeline :events="store.selectedEntityTimeline" />
        </div>

        <div class="drawer-section">
          <h4>提及章节 ({{ store.selectedEntityMentions.length }})</h4>
          <EntityMentions :mentions="store.selectedEntityMentions" />
        </div>

        <div class="drawer-section">
          <h4>实体关系 ({{ store.selectedEntityRelations.length }})</h4>
          <EntityRelations :relations="store.selectedEntityRelations" :entity-name="store.selectedEntity.name" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}

.drawer-panel {
  width: 480px;
  max-width: 90vw;
  background: var(--surface-solid);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
}

.drawer-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--muted);
  padding: 0 4px;
  line-height: 1;
}

.btn-close:hover {
  color: var(--text);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.entity-card {
  padding: 16px;
  background: var(--bg);
  border-radius: 12px;
  margin-bottom: 16px;
}

.entity-name {
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.entity-meta {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.8;
}

.candidate-tag {
  font-size: 11px;
  color: var(--warning);
  border: 1px solid var(--warning);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 4px;
}

.drawer-section {
  margin-bottom: 20px;
}

.drawer-section h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text);
}
</style>
