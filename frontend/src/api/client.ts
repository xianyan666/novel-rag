import type { ProjectConfig, QueryResponse, TimelineEventInfo, EntityInfo, EntityMention, EntityTimelineEvent, EntityRelation, WorldInfo } from '../types/api'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, options)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(body.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export function listProjects(): Promise<ProjectConfig[]> {
  return request('/projects')
}

export function scanProject(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/scan`, { method: 'POST' })
}

export function ingestProject(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/ingest`, { method: 'POST' })
}

export function buildIndex(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/index`, { method: 'POST' })
}

export function queryProject(projectId: string, question: string, topK?: number): Promise<QueryResponse> {
  return request(`/projects/${projectId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK }),
  })
}

export function buildTimeline(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/timeline/build`, { method: 'POST' })
}

export function getTimelineEvents(projectId: string): Promise<{ events: TimelineEventInfo[], count: number }> {
  return request(`/projects/${projectId}/timeline/events`)
}

export function buildWorldIndex(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/worlds/build`, { method: 'POST' })
}

export function listWorlds(projectId: string): Promise<{ worlds: WorldInfo[], count: number }> {
  return request(`/projects/${projectId}/worlds`)
}

export function buildEntities(projectId: string): Promise<any> {
  return request(`/projects/${projectId}/entities/build`, { method: 'POST' })
}

export function listEntities(projectId: string, entityType?: string): Promise<{ entities: EntityInfo[], count: number }> {
  const params = entityType ? `?entity_type=${entityType}` : ''
  return request(`/projects/${projectId}/entities${params}`)
}

export function searchEntities(projectId: string, q: string): Promise<{ entities: EntityInfo[], count: number }> {
  return request(`/projects/${projectId}/entities/search?q=${encodeURIComponent(q)}`)
}

export function getEntity(projectId: string, entityId: string): Promise<EntityInfo> {
  return request(`/projects/${projectId}/entities/${entityId}`)
}

export function getEntityMentions(projectId: string, entityId: string): Promise<{ mentions: EntityMention[], count: number }> {
  return request(`/projects/${projectId}/entities/${entityId}/mentions`)
}

export function getEntityTimeline(projectId: string, entityId: string): Promise<{ timeline: EntityTimelineEvent[], count: number }> {
  return request(`/projects/${projectId}/entities/${entityId}/timeline`)
}

export function getEntityRelations(projectId: string, entityId: string): Promise<{ relations: EntityRelation[], count: number }> {
  return request(`/projects/${projectId}/entities/${entityId}/relations`)
}

export function queryRelations(projectId: string, source?: string, target?: string): Promise<{ relations: EntityRelation[], count: number }> {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (target) params.set('target', target)
  const qs = params.toString()
  return request(`/projects/${projectId}/relations${qs ? '?' + qs : ''}`)
}
