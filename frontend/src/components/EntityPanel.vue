<script setup lang="ts">
import { onMounted } from 'vue'
import { useProjectStore } from '../stores/projectStore'
import EntitySearch from './EntitySearch.vue'
import EvidenceBadge from './EvidenceBadge.vue'

const store = useProjectStore()

onMounted(async () => {
  if (store.currentId && store.entityCount === 0) {
    await store.loadEntityStats()
  }
})

const typeLabels: Record<string, string> = {
  character: '人物',
  item: '物品',
  skill: '技能',
  place: '地点',
  faction: '势力',
  world: '世界',
  concept: '概念',
  title: '称号',
}
</script>

<template>
  <div class="entity-panel">
    <div class="card">
      <h3>实体库</h3>
      <div class="stats" v-if="store.entityCount > 0">
        <div class="stat-item">
          <span class="stat-value">{{ store.entityCount }}</span>
          <span class="stat-label">实体</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ store.entityMentionCount }}</span>
          <span class="stat-label">提及</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ store.entityTimelineCount }}</span>
          <span class="stat-label">时间线</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ store.entityRelationCount }}</span>
          <span class="stat-label">关系</span>
        </div>
      </div>
      <div v-else class="empty-hint">
        暂无实体数据，请先构建实体索引
      </div>
    </div>

    <div class="card">
      <EntitySearch />
      <div class="entity-list" v-if="store.entities.length">
        <div
          v-for="ent in store.entities"
          :key="ent.entity_id"
          class="entity-item"
          @click="store.openEntityDetail(ent.entity_id)"
        >
          <div class="entity-name">
            {{ ent.name }}
            <EvidenceBadge :type="ent.type" :label="typeLabels[ent.type] || ent.type" />
            <span v-if="ent.status === 'candidate'" class="candidate-tag">候选</span>
          </div>
          <div class="entity-meta">
            <span v-if="ent.first_seen_chapter">第{{ ent.first_seen_chapter }}章</span>
            <span v-if="ent.aliases?.length">别名: {{ ent.aliases.join(', ') }}</span>
          </div>
        </div>
      </div>
      <div v-else-if="store.entityCount > 0" class="empty-hint">
        搜索实体或点击上方统计查看详情
      </div>
    </div>
  </div>
</template>

<style scoped>
.entity-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 8px;
}

.stat-item {
  text-align: center;
  padding: 8px;
  background: var(--surface);
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--accent);
}

.stat-label {
  font-size: 11px;
  color: var(--muted);
}

.entity-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.entity-item {
  padding: 10px 12px;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: border-color 0.15s;
}

.entity-item:hover {
  border-color: var(--accent);
}

.entity-name {
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.entity-meta {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  display: flex;
  gap: 12px;
}

.candidate-tag {
  font-size: 11px;
  color: var(--warning);
  border: 1px solid var(--warning);
  padding: 1px 6px;
  border-radius: 4px;
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}
</style>
