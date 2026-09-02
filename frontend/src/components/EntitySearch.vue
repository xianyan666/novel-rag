<script setup lang="ts">
import { ref } from 'vue'
import { useProjectStore } from '../stores/projectStore'

const store = useProjectStore()
const query = ref('')

async function doSearch() {
  if (!query.value.trim()) return
  await store.searchEntity(query.value)
}
</script>

<template>
  <div class="entity-search">
    <input
      v-model="query"
      placeholder="搜索实体，例如：杨间"
      @keydown.enter="doSearch"
    />
    <button class="btn btn-sm" :disabled="store.loading || !query.trim()" @click="doSearch">
      搜索
    </button>
  </div>
</template>

<style scoped>
.entity-search {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.entity-search input {
  flex: 1;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}
</style>
