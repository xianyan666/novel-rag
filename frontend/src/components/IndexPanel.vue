<script setup lang="ts">
import { useProjectStore } from '../stores/projectStore'

const store = useProjectStore()
</script>

<template>
  <div class="card">
    <h3>索引管理</h3>
    <div class="btn-group">
      <button class="btn btn-secondary" :disabled="store.loading || !store.currentId" @click="store.scan()">
        扫描原文
      </button>
      <button class="btn btn-secondary" :disabled="store.loading || !store.currentId" @click="store.ingest()">
        解析导入
      </button>
      <button class="btn" :disabled="store.loading || !store.currentId" @click="store.index()">
        <span v-if="store.loading" class="spinner"></span>
        构建索引
      </button>
      <button class="btn btn-secondary" :disabled="store.loading || !store.currentId" @click="store.buildTimeline()">
        构建时间线索引
      </button>
      <button class="btn btn-secondary" :disabled="store.loading || !store.currentId" @click="store.buildWorldIndex()">
        构建世界索引
      </button>
      <button class="btn btn-accent" :disabled="store.loading || !store.currentId" @click="store.buildEntities()">
        <span v-if="store.loading" class="spinner"></span>
        构建实体索引
      </button>
    </div>
    <div class="index-stats" style="margin-top: 8px; font-size: 13px; opacity: 0.7;">
      <span v-if="store.timelineEventCount > 0">时间线事件: {{ store.timelineEventCount }} 条</span>
      <span v-if="store.worldCount > 0" style="margin-left: 16px;">世界候选: {{ store.worldCount }}</span>
      <span v-if="store.entityCount > 0" style="margin-left: 16px;">实体: {{ store.entityCount }} | 提及: {{ store.entityMentionCount }} | 时间线: {{ store.entityTimelineCount }} | 关系: {{ store.entityRelationCount }}</span>
    </div>
    <div v-if="store.actionLog" class="log-box" style="margin-top: 12px;">
      {{ store.actionLog }}
    </div>
    <div v-if="store.error" class="error-box" style="margin-top: 8px;">
      {{ store.error }}
    </div>
  </div>

  <div class="card" v-if="store.current()?.report">
    <h3>导入报告</h3>
    <div style="font-size: 13px; line-height: 2;">
      <div>源文件: {{ store.current()!.report!.source_files.length }} 个</div>
      <div>章节数: {{ store.current()!.report!.chapter_count }}</div>
      <div v-if="store.current()!.report!.chunk_count">切片数: {{ store.current()!.report!.chunk_count }}</div>
      <div>章节范围: {{ store.current()!.report!.first_chapter_no }} - {{ store.current()!.report!.last_chapter_no }}</div>
      <div v-if="store.current()!.report!.missing_chapter_numbers.length" style="color: var(--warning);">
        缺失章节: {{ store.current()!.report!.missing_chapter_numbers.join(', ') }}
      </div>
      <div v-if="store.current()!.report!.duplicate_chapter_numbers.length" style="color: var(--warning);">
        重复章节: {{ store.current()!.report!.duplicate_chapter_numbers.join(', ') }}
      </div>
      <div v-if="store.current()!.report!.warnings.length" style="color: var(--warning);">
        警告: {{ store.current()!.report!.warnings.length }} 条
      </div>
    </div>
  </div>
</template>
