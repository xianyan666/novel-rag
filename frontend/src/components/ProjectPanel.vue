<script setup lang="ts">
import { useProjectStore } from '../stores/projectStore'

const store = useProjectStore()

function statusBadge(p: any) {
  if (p.has_index) return { text: '已索引', cls: 'badge-ok' }
  if (p.has_chunks) return { text: '已切分', cls: 'badge-warn' }
  if (p.has_chapters) return { text: '已解析', cls: 'badge-warn' }
  return { text: '未导入', cls: 'badge-none' }
}
</script>

<template>
  <div class="card">
    <h3>项目列表</h3>
    <div v-if="store.projects.length === 0" class="empty-state">
      暂无项目
    </div>
    <div
      v-for="p in store.projects"
      :key="p.project_id"
      class="project-item"
      :class="{ active: p.project_id === store.currentId }"
      @click="store.currentId = p.project_id"
    >
      <div class="name">
        {{ p.display_name }}
        <span class="badge" :class="statusBadge(p).cls">{{ statusBadge(p).text }}</span>
      </div>
      <div class="meta">{{ p.source_dir }}</div>
    </div>
  </div>

  <div class="card" v-if="store.current()">
    <h3>项目详情</h3>
    <div style="font-size: 13px; line-height: 2;">
      <div>ID: {{ store.current()!.project_id }}</div>
      <div>原文目录: {{ store.current()!.source_dir }}</div>
      <div v-if="store.current()!.report">
        章节: {{ store.current()!.report!.chapter_count }}
        <span v-if="store.current()!.report!.chunk_count">
          | 切片: {{ store.current()!.report!.chunk_count }}
        </span>
      </div>
      <div v-if="store.current()!.report?.missing_chapter_numbers?.length" style="color: var(--warning);">
        缺失章节: {{ store.current()!.report!.missing_chapter_numbers.length }}
      </div>
    </div>
  </div>
</template>
