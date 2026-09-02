import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ProjectConfig, QueryResponse, EntityInfo, EntityMention, EntityTimelineEvent, EntityRelation, WorldInfo } from '../types/api'
import * as api from '../api/client'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<ProjectConfig[]>([])
  const currentId = ref<string>('')
  const loading = ref(false)
  const error = ref('')
  const queryResult = ref<QueryResponse | null>(null)
  const actionLog = ref<string>('')
  const timelineEventCount = ref(0)
  const worlds = ref<WorldInfo[]>([])
  const worldCount = ref(0)

  // Entity state
  const entities = ref<EntityInfo[]>([])
  const entityCount = ref(0)
  const entityMentionCount = ref(0)
  const entityTimelineCount = ref(0)
  const entityRelationCount = ref(0)
  const selectedEntity = ref<EntityInfo | null>(null)
  const selectedEntityMentions = ref<EntityMention[]>([])
  const selectedEntityTimeline = ref<EntityTimelineEvent[]>([])
  const selectedEntityRelations = ref<EntityRelation[]>([])
  const entityDrawerOpen = ref(false)

  const current = () => projects.value.find(p => p.project_id === currentId.value)

  async function loadProjects() {
    try {
      projects.value = await api.listProjects()
      if (!currentId.value && projects.value.length > 0) {
        currentId.value = projects.value[0].project_id
      }
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function scan() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    try {
      const result = await api.scanProject(currentId.value)
      actionLog.value = `扫描完成: ${result.txt_files.length} 个文件, ${result.total_size_mb} MB`
      await loadProjects()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function ingest() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    actionLog.value = '正在导入...'
    try {
      const result = await api.ingestProject(currentId.value)
      const r = result.report
      actionLog.value = `导入完成: ${r.chapter_count} 章节, ${r.chunk_count || 0} 切片`
      if (r.missing_chapter_numbers?.length) {
        actionLog.value += `, 缺失 ${r.missing_chapter_numbers.length} 章`
      }
      await loadProjects()
    } catch (e: any) {
      error.value = e.message
      actionLog.value = ''
    } finally {
      loading.value = false
    }
  }

  async function index() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    actionLog.value = '正在构建索引...'
    try {
      await api.buildIndex(currentId.value)
      actionLog.value = '索引构建完成'
      await loadProjects()
    } catch (e: any) {
      error.value = e.message
      actionLog.value = ''
    } finally {
      loading.value = false
    }
  }

  async function query(question: string, topK?: number) {
    if (!currentId.value || !question.trim()) return
    loading.value = true
    error.value = ''
    queryResult.value = null
    try {
      queryResult.value = await api.queryProject(currentId.value, question, topK)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function buildTimeline() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    actionLog.value = '正在构建时间线索引...'
    try {
      await api.buildTimeline(currentId.value)
      actionLog.value = '时间线索引构建完成'
      await loadTimelineCount()
    } catch (e: any) {
      error.value = e.message
      actionLog.value = ''
    } finally {
      loading.value = false
    }
  }

  async function loadTimelineCount() {
    if (!currentId.value) return
    try {
      const result = await api.getTimelineEvents(currentId.value)
      timelineEventCount.value = result.count
    } catch {
      timelineEventCount.value = 0
    }
  }

  async function buildWorldIndex() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    actionLog.value = '正在构建世界索引...'
    try {
      await api.buildWorldIndex(currentId.value)
      await loadWorldStats()
      actionLog.value = `世界索引构建完成: ${worldCount.value} 个候选世界`
    } catch (e: any) {
      error.value = e.message
      actionLog.value = ''
    } finally {
      loading.value = false
    }
  }

  async function loadWorldStats() {
    if (!currentId.value) return
    try {
      const result = await api.listWorlds(currentId.value)
      worlds.value = result.worlds
      worldCount.value = result.count
    } catch {
      worlds.value = []
      worldCount.value = 0
    }
  }

  async function buildEntities() {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    actionLog.value = '正在构建实体索引...'
    try {
      await api.buildEntities(currentId.value)
      actionLog.value = '实体索引构建完成'
      await loadEntityStats()
    } catch (e: any) {
      error.value = e.message
      actionLog.value = ''
    } finally {
      loading.value = false
    }
  }

  async function loadEntityStats() {
    if (!currentId.value) return
    try {
      const result = await api.listEntities(currentId.value)
      entityCount.value = result.count
      entities.value = result.entities
    } catch {
      entityCount.value = 0
      entities.value = []
    }
    // Load counts for mentions, timeline, relations from entity index
    try {
      const allEntities = entities.value
      let mCount = 0
      let tCount = 0
      let rCount = 0
      for (const ent of allEntities.slice(0, 5)) {
        const [m, t, r] = await Promise.all([
          api.getEntityMentions(currentId.value, ent.entity_id),
          api.getEntityTimeline(currentId.value, ent.entity_id),
          api.getEntityRelations(currentId.value, ent.entity_id),
        ])
        mCount += m.count
        tCount += t.count
        rCount += r.count
      }
      entityMentionCount.value = mCount
      entityTimelineCount.value = tCount
      entityRelationCount.value = rCount
    } catch {
      // ignore
    }
  }

  async function searchEntity(q: string) {
    if (!currentId.value) return
    loading.value = true
    error.value = ''
    try {
      const result = await api.searchEntities(currentId.value, q)
      entities.value = result.entities
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function openEntityDetail(entityId: string) {
    if (!currentId.value) return
    try {
      const [ent, mentions, timeline, relations] = await Promise.all([
        api.getEntity(currentId.value, entityId),
        api.getEntityMentions(currentId.value, entityId),
        api.getEntityTimeline(currentId.value, entityId),
        api.getEntityRelations(currentId.value, entityId),
      ])
      selectedEntity.value = ent
      selectedEntityMentions.value = mentions.mentions
      selectedEntityTimeline.value = timeline.timeline
      selectedEntityRelations.value = relations.relations
      entityDrawerOpen.value = true
    } catch (e: any) {
      error.value = e.message
    }
  }

  function closeEntityDrawer() {
    entityDrawerOpen.value = false
    selectedEntity.value = null
    selectedEntityMentions.value = []
    selectedEntityTimeline.value = []
    selectedEntityRelations.value = []
  }

  return {
    projects, currentId, loading, error, queryResult, actionLog, timelineEventCount, worlds, worldCount,
    entities, entityCount, entityMentionCount, entityTimelineCount, entityRelationCount,
    selectedEntity, selectedEntityMentions, selectedEntityTimeline, selectedEntityRelations,
    entityDrawerOpen,
    current, loadProjects, scan, ingest, index, query, buildTimeline, loadTimelineCount, buildWorldIndex, loadWorldStats,
    buildEntities, loadEntityStats, searchEntity, openEntityDetail, closeEntityDrawer,
  }
})
