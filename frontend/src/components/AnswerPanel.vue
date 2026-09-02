<script setup lang="ts">
import { ref } from 'vue'
import { useProjectStore } from '../stores/projectStore'
import EvidenceBadge from './EvidenceBadge.vue'
import EntityTimeline from './EntityTimeline.vue'
import EntityRelations from './EntityRelations.vue'

const store = useProjectStore()
const expandedChunks = ref<Set<string>>(new Set())
const showDebug = ref(false)

function toggleChunk(chunkId: string) {
  if (expandedChunks.value.has(chunkId)) {
    expandedChunks.value.delete(chunkId)
  } else {
    expandedChunks.value.add(chunkId)
  }
}

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
  <div v-if="store.queryResult">
    <!-- 问题分析 -->
    <div class="card" v-if="store.queryResult.query_analysis">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h3>问题分析</h3>
        <button class="btn btn-secondary" style="font-size: 12px; padding: 2px 8px;" @click="showDebug = !showDebug">
          {{ showDebug ? '隐藏调试' : '显示调试' }}
        </button>
      </div>
      <div style="font-size: 13px; line-height: 2;">
        <div>问题类型: <span class="tag">{{ store.queryResult.query_analysis.query_type }}</span></div>
        <div v-if="store.queryResult.query_analysis.entities.length">
          识别实体: {{ store.queryResult.query_analysis.entities.join(', ') }}
        </div>
        <div v-if="store.queryResult.query_analysis.event_hints.length">
          事件提示: {{ store.queryResult.query_analysis.event_hints.join(', ') }}
        </div>
        <div v-if="store.queryResult.query_analysis.time_constraint">
          时间约束: {{ store.queryResult.query_analysis.time_constraint }}
        </div>
      </div>
    </div>

    <!-- 证据不足警告 -->
    <div class="card" v-if="store.queryResult.retrieval_debug?.warnings?.length" style="border-color: var(--warning);">
      <h3 style="color: var(--warning);">证据警告</h3>
      <div style="font-size: 13px;">
        <div v-for="w in store.queryResult.retrieval_debug.warnings" :key="w">{{ w }}</div>
      </div>
    </div>

    <!-- 识别到的实体 -->
    <div class="card" v-if="store.queryResult.entity_analysis?.matched_entities?.length">
      <h3>识别到的实体</h3>
      <div class="entity-chips">
        <div
          v-for="ent in store.queryResult.entity_analysis.matched_entities"
          :key="ent.entity_id"
          class="entity-chip"
          @click="store.openEntityDetail(ent.entity_id)"
        >
          <EvidenceBadge :type="ent.type" :label="typeLabels[ent.type] || ent.type" />
          <span class="chip-name">{{ ent.name }}</span>
          <span class="chip-confidence">{{ ent.confidence.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- 实体时间线 -->
    <div class="card" v-if="store.queryResult.entity_timeline?.length">
      <h3>实体时间线 ({{ store.queryResult.entity_timeline.length }})</h3>
      <EntityTimeline :events="store.queryResult.entity_timeline" />
    </div>

    <!-- 实体关系 -->
    <div class="card" v-if="store.queryResult.entity_relations?.length">
      <h3>实体关系 ({{ store.queryResult.entity_relations.length }})</h3>
      <EntityRelations :relations="store.queryResult.entity_relations" />
    </div>

    <!-- 实体提及 -->
    <div class="card" v-if="store.queryResult.entity_mentions?.length">
      <h3>实体提及 ({{ store.queryResult.entity_mentions.length }})</h3>
      <div
        v-for="m in store.queryResult.entity_mentions.slice(0, 5)"
        :key="m.mention_id"
        class="chunk-item"
      >
        <div class="chunk-meta">
          第{{ m.chapter_no }}章 {{ m.chapter_title }}
          <span v-if="m.confidence" style="margin-left: 8px; opacity: 0.6;">置信度: {{ m.confidence.toFixed(2) }}</span>
        </div>
        <div class="chunk-text" v-if="m.evidence">{{ m.evidence }}</div>
      </div>
    </div>

    <!-- 受保护结论 -->
    <div class="card protected-card" v-if="store.queryResult.protected_answer">
      <h3 style="color: var(--success);">受保护结论</h3>
      <div class="protected-content">
        <div class="protected-entity">
          <EvidenceBadge :type="store.queryResult.protected_answer.source" :label="store.queryResult.protected_answer.type === 'entity_first_seen' ? '首次出现' : store.queryResult.protected_answer.type" />
          <span class="protected-name">{{ store.queryResult.protected_answer.entity_name }}</span>
        </div>
        <div class="protected-chapter">
          第{{ store.queryResult.protected_answer.chapter_no }}章 {{ store.queryResult.protected_answer.chapter_title }}
        </div>
        <div class="protected-score">
          来源: {{ store.queryResult.protected_answer.source }} | final_score={{ store.queryResult.protected_answer.final_score.toFixed(2) }}
        </div>
      </div>
    </div>

    <!-- 实体证据权重 -->
    <div class="card" v-if="store.queryResult.evidence_scores?.length && showDebug">
      <h3>实体证据权重</h3>
      <div class="evidence-scores">
        <div
          v-for="(es, idx) in store.queryResult.evidence_scores"
          :key="idx"
          class="evidence-score-item"
          :class="{ 'is-protected': es.protected }"
        >
          <div class="score-header">
            <EvidenceBadge :type="es.protected ? 'protected' : es.source" :label="es.protected ? 'protected' : es.source" />
            <span class="score-chunk">{{ es.chunk_id }}</span>
          </div>
          <div class="score-details">
            <span v-if="es.entity_score != null">entity={{ es.entity_score.toFixed(2) }}</span>
            <span v-if="es.order_score != null">order={{ es.order_score.toFixed(2) }}</span>
            <span v-if="es.keyword_score != null">keyword={{ es.keyword_score.toFixed(2) }}</span>
            <span v-if="es.vector_score != null">vector={{ es.vector_score.toFixed(2) }}</span>
            <span v-if="es.confidence_score != null">conf={{ es.confidence_score.toFixed(2) }}</span>
            <span class="score-final">final={{ es.final_score.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 回答 -->
    <div class="card">
      <h3>回答</h3>
      <div class="answer-text">{{ store.queryResult.answer }}</div>
    </div>

    <!-- 引用章节 -->
    <div class="card" v-if="store.queryResult.citations.length">
      <h3>引用章节</h3>
      <ul class="citation-list">
        <li v-for="c in store.queryResult.citations" :key="c.chunk_id">
          第{{ c.chapter_no }}章 {{ c.chapter_title }}
        </li>
      </ul>
    </div>

    <!-- 调试信息 -->
    <div class="card" v-if="showDebug && store.queryResult.retrieval_debug">
      <h3>检索路由</h3>
      <div style="font-size: 13px; line-height: 2;">
        <div>路由: {{ store.queryResult.retrieval_debug.route }}</div>
        <div>向量召回: {{ store.queryResult.retrieval_debug.vector_count }}</div>
        <div>时间线召回: {{ store.queryResult.retrieval_debug.timeline_count }}</div>
        <div>关键词召回: {{ store.queryResult.retrieval_debug.keyword_count }}</div>
        <div v-if="store.queryResult.retrieval_debug.matched_worlds?.length">
          世界过滤: {{ store.queryResult.retrieval_debug.matched_worlds.map(world => world.name).join(', ') }}
        </div>
        <div v-if="store.queryResult.retrieval_debug.warnings?.length" style="color: var(--warning);">
          警告: {{ store.queryResult.retrieval_debug.warnings.join('; ') }}
        </div>
      </div>
    </div>

    <!-- 时间线候选 -->
    <div class="card" v-if="store.queryResult.timeline_events?.length">
      <h3>时间线候选 ({{ store.queryResult.timeline_events.length }})</h3>
      <div
        v-for="evt in store.queryResult.timeline_events"
        :key="evt.event_id"
        class="chunk-item"
      >
        <div class="chunk-meta">
          <span class="tag">{{ evt.event_type }}</span>
          第{{ evt.chapter_no }}章 {{ evt.chapter_title }}
          <span v-if="evt.confidence" style="margin-left: 8px; opacity: 0.6;">置信度: {{ evt.confidence }}</span>
        </div>
        <div class="chunk-text">{{ evt.event_summary }}</div>
      </div>
    </div>

    <!-- 命中片段 -->
    <div class="card" v-if="store.queryResult.retrieved_chunks.length">
      <h3>命中片段 ({{ store.queryResult.retrieved_chunks.length }})</h3>
      <div
        v-for="chunk in store.queryResult.retrieved_chunks"
        :key="chunk.chunk_id"
        class="chunk-item"
        :class="{ expanded: expandedChunks.has(chunk.chunk_id) }"
        @click="toggleChunk(chunk.chunk_id)"
      >
        <div class="chunk-meta">
          第{{ chunk.chapter_no }}章 {{ chunk.chapter_title }}
          <span style="margin-left: 8px; opacity: 0.6;">{{ chunk.chunk_id }}</span>
          <span v-if="chunk.world_name" style="margin-left: 8px; opacity: 0.6;">世界: {{ chunk.world_name }}</span>
        </div>
        <div class="chunk-text">{{ chunk.text_preview }}</div>
      </div>
    </div>
  </div>

  <div v-else-if="!store.loading" class="empty-state">
    选择项目并输入问题开始查询
  </div>
</template>

<style scoped>
.entity-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.entity-chip:hover {
  border-color: var(--accent);
}

.chip-name {
  font-size: 13px;
  font-weight: 500;
}

.chip-confidence {
  font-size: 11px;
  color: var(--muted);
}

.protected-card {
  border-color: var(--success) !important;
  border-width: 2px;
}

.protected-content {
  font-size: 14px;
  line-height: 1.8;
}

.protected-entity {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.protected-name {
  font-weight: 600;
  font-size: 15px;
}

.protected-chapter {
  font-size: 14px;
  color: var(--text);
}

.protected-score {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

.evidence-scores {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-score-item {
  padding: 8px 10px;
  background: var(--bg);
  border-radius: 8px;
  border: 1px solid transparent;
}

.evidence-score-item.is-protected {
  border-color: var(--success);
  background: rgba(32, 161, 98, 0.05);
}

.score-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.score-chunk {
  font-size: 11px;
  color: var(--muted);
  font-family: monospace;
}

.score-details {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
}

.score-final {
  font-weight: 600;
  color: var(--text);
}
</style>
