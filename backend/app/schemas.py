"""Pydantic 数据模型。"""

from pydantic import BaseModel


class ProjectInfo(BaseModel):
    project_id: str
    display_name: str
    source_dir: str


class IngestReport(BaseModel):
    project_id: str
    source_files: list[str]
    chapter_count: int
    chunk_count: int | None = None
    first_chapter_no: int | None = None
    last_chapter_no: int | None = None
    duplicate_chapter_numbers: list[int] = []
    missing_chapter_numbers: list[int] = []
    warnings: list[str] = []


class QueryRequest(BaseModel):
    question: str
    mode: str = "evidence"
    top_k: int | None = None


class Citation(BaseModel):
    chapter_no: int
    chapter_title: str
    chunk_id: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    chapter_no: int
    chapter_title: str
    text_preview: str


class QueryAnalysis(BaseModel):
    query_type: str
    entities: list[str] = []
    event_hints: list[str] = []
    time_constraint: str | None = None
    confidence: float = 0.5


class TimelineEventResponse(BaseModel):
    event_id: str
    event_type: str
    chapter_no: int
    chapter_title: str
    event_summary: str
    evidence: str | None = None
    confidence: float | None = None


class RetrievalDebug(BaseModel):
    route: str
    vector_count: int = 0
    timeline_count: int = 0
    keyword_count: int = 0
    warnings: list[str] = []


class EntityInfo(BaseModel):
    entity_id: str
    name: str
    type: str
    subtype: str = ""
    aliases: list[str] = []
    first_seen_chapter: int | None = None
    first_seen_title: str | None = None
    confidence: float = 0
    status: str = ""


class EntityMentionResponse(BaseModel):
    mention_id: str
    entity_id: str
    name: str
    chapter_no: int
    chapter_title: str
    chunk_id: str
    evidence: str
    confidence: float


class EntityTimelineEventResponse(BaseModel):
    entity_event_id: str
    entity_id: str
    entity_name: str
    event_type: str
    chapter_no: int
    chapter_title: str
    summary: str
    evidence: str
    related_entities: list[str] = []
    confidence: float


class EntityRelationResponse(BaseModel):
    relation_id: str
    source_entity_id: str
    source_name: str
    target_entity_id: str
    target_name: str
    relation_type: str
    chapter_no: int
    chapter_title: str
    evidence: str
    confidence: float
    status: str


class EntityAnalysis(BaseModel):
    matched_entities: list[EntityInfo] = []
    entity_query_type: str = ""


class ProtectedAnswer(BaseModel):
    type: str
    entity_id: str = ""
    entity_name: str = ""
    chapter_no: int = 0
    chapter_title: str = ""
    chunk_id: str = ""
    source: str = ""
    final_score: float = 0


class EvidenceScore(BaseModel):
    chunk_id: str
    source: str
    entity_score: float | None = None
    order_score: float | None = None
    keyword_score: float | None = None
    vector_score: float | None = None
    confidence_score: float | None = None
    final_score: float = 0
    protected: bool = False
    relation_type: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    query_analysis: QueryAnalysis | None = None
    timeline_events: list[TimelineEventResponse] = []
    entity_analysis: EntityAnalysis | None = None
    entity_mentions: list[EntityMentionResponse] = []
    entity_timeline: list[EntityTimelineEventResponse] = []
    entity_relations: list[EntityRelationResponse] = []
    protected_answer: ProtectedAnswer | None = None
    evidence_scores: list[EvidenceScore] = []
    retrieval_debug: RetrievalDebug | None = None
