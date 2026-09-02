<script setup lang="ts">
import { ref } from 'vue'
import { useProjectStore } from '../stores/projectStore'

const store = useProjectStore()
const question = ref('')
const topK = ref(8)

async function doQuery() {
  await store.query(question.value, topK.value)
}
</script>

<template>
  <div class="card">
    <h3>查询</h3>
    <div class="form-row">
      <textarea
        v-model="question"
        placeholder="输入问题，例如：杨间第一次遇到鬼是在什么情况下？"
        @keydown.ctrl.enter="doQuery"
      ></textarea>
    </div>
    <div class="form-row">
      <label>Top K</label>
      <input v-model.number="topK" type="number" min="1" max="20" style="width: 80px;" />
      <button class="btn" :disabled="store.loading || !store.currentId || !question.trim()" @click="doQuery">
        <span v-if="store.loading" class="spinner"></span>
        查询
      </button>
    </div>
    <div v-if="store.error" class="error-box" style="margin-top: 8px;">
      {{ store.error }}
    </div>
  </div>
</template>
