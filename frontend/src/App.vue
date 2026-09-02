<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useProjectStore } from './stores/projectStore'
import ProjectPanel from './components/ProjectPanel.vue'
import IndexPanel from './components/IndexPanel.vue'
import QueryPanel from './components/QueryPanel.vue'
import AnswerPanel from './components/AnswerPanel.vue'
import EntityPanel from './components/EntityPanel.vue'
import EntityDetailDrawer from './components/EntityDetailDrawer.vue'

const store = useProjectStore()
const activeTab = ref<'project' | 'index' | 'query' | 'entity'>('query')

onMounted(async () => {
  await store.loadProjects()
  await Promise.all([store.loadTimelineCount(), store.loadWorldStats()])
})
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <h1>小说 RAG 知识库</h1>
      <div class="header-info">
        <span class="status" v-if="store.current()">
          {{ store.current()!.display_name }}
        </span>
        <span class="status dim" v-if="store.entityCount > 0">
          实体: {{ store.entityCount }}
        </span>
      </div>
    </header>

    <aside class="sidebar">
      <nav class="sidebar-nav">
        <button
          class="nav-item"
          :class="{ active: activeTab === 'project' }"
          @click="activeTab = 'project'"
        >项目</button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'index' }"
          @click="activeTab = 'index'"
        >数据索引</button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'query' }"
          @click="activeTab = 'query'"
        >问答</button>
        <button
          class="nav-item"
          :class="{ active: activeTab === 'entity' }"
          @click="activeTab = 'entity'; store.loadEntityStats()"
        >实体库</button>
      </nav>

      <div class="sidebar-content">
        <ProjectPanel />
      </div>
    </aside>

    <main class="main-area">
      <template v-if="activeTab === 'query'">
        <QueryPanel />
        <AnswerPanel />
      </template>
      <template v-else-if="activeTab === 'index'">
        <IndexPanel />
      </template>
      <template v-else-if="activeTab === 'entity'">
        <EntityPanel />
      </template>
    </main>

    <EntityDetailDrawer />
  </div>
</template>
