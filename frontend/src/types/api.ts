export interface ProjectConfig {
  project_id: string
  display_name: string
  source_dir: string
  source_exists?: boolean
  has_chapters?: boolean
  has_chunks?: boolean
  has_index?: boolean
  report?: IngestReport
}

export interface IngestReport {
  project_id: string
  source_files: string[]
  chapter_count: number
  chunk_count?: number
  first_chapter_no?: number
  last_chapter_no?: number
  duplicate_chapter_numbers: number[]
  missing_chapter_numbers: number[]
  warnings: string[]
}

export interface Citation {
  chapter_no: number
  chapter_title: string
  chunk_id: string
}

export interface RetrievedChunk {
  chunk_id: string
  chapter_no: number
  chapter_title: string
  text_preview: string
  world_id?: string
  world_name?: string
}

export interface QueryAnalysis {
  query_type: string
  entities: string[]
  event_hints: string[]
  time_constraint?: string
  confidence: number
}

export interface TimelineEventInfo {
  event_id: string
  event_type: string
  chapter_no: number
  chapter_title: string
  event_summary: string
  evidence?: string
  confidence?: number
}

export interface TimelineEdgeInfo {
  edge_id: string
  from_event_id: string
  to_event_id: string
  relation: string
  from_chapter_no?: number
  to_chapter_no?: number
  evidence?: string
  confidence?: number
}

export interface RetrievalDebug {
  route: string
  vector_count: number
  timeline_count: number
  keyword_count: number
  world_filter_count?: number
  matched_worlds?: Array<{ world_id: string, name: string }>
  warnings?: string[]
}

export interface WorldInfo {
  world_id: string
  name: string
  aliases: string[]
  start_chapter: number
  end_chapter: number
  confidence: number
  status: string
  boundary_signal?: string
}

export interface EntityInfo {
  entity_id: string
  name: string
  type: string
  subtype?: string
  aliases: string[]
  first_seen_chapter?: number
  first_seen_title?: string
  confidence: number
  status: string
}

export interface EntityMention {
  mention_id: string
  entity_id: string
  name: string
  chapter_no: number
  chapter_title: string
  chunk_id: string
  evidence: string
  confidence: number
}

export interface EntityTimelineEvent {
  entity_event_id: string
  entity_id: string
  entity_name: string
  event_type: string
  chapter_no: number
  chapter_title: string
  summary: string
  evidence: string
  related_entities: string[]
  confidence: number
}

export interface EntityRelation {
  relation_id: string
  source_entity_id: string
  source_name: string
  target_entity_id: string
  target_name: string
  relation_type: string
  chapter_no: number
  chapter_title: string
  evidence: string
  confidence: number
  status: string
}

export interface EntityAnalysis {
  matched_entities: EntityInfo[]
  entity_query_type: string
}

export interface ProtectedAnswer {
  type: string
  entity_id: string
  entity_name: string
  chapter_no: number
  chapter_title: string
  chunk_id: string
  source: string
  final_score: number
}

export interface EvidenceScore {
  chunk_id: string
  source: string
  entity_score?: number
  order_score?: number
  keyword_score?: number
  vector_score?: number
  confidence_score?: number
  final_score: number
  protected: boolean
  relation_type?: string
}

export interface QueryResponse {
  answer: string
  citations: Citation[]
  retrieved_chunks: RetrievedChunk[]
  query_analysis?: QueryAnalysis
  timeline_events?: TimelineEventInfo[]
  entity_analysis?: EntityAnalysis
  entity_mentions?: EntityMention[]
  entity_timeline?: EntityTimelineEvent[]
  entity_relations?: EntityRelation[]
  protected_answer?: ProtectedAnswer
  evidence_scores?: EvidenceScore[]
  retrieval_debug?: RetrievalDebug
}
