from __future__ import annotations

from pydantic import BaseModel

class StudySourceLinkRequest(BaseModel):
    material_id: str
    revision_id: str
    extraction_id: str | None = None
    chunk_id: str
    span_id: str | None = None
    citation_key: str | None = None

class NoteSourceLinkRequest(BaseModel):
    material_id: str
    revision_id: str
    extraction_id: str
    chunk_id: str
    span_id: str | None = None
    citation_key: str
    context_chunk_ids: list[str]

class RhythmSettingsRequest(BaseModel):
    cadence: str
    timezone: str
    period_start: str
    target_minutes: int

class RhythmAllocationRequest(BaseModel):
    item_id: str
    local_date: str
    planned_minutes: int

class RhythmAllocationPatchRequest(BaseModel):
    local_date: str | None = None
    planned_minutes: int | None = None

class NoteRequest(BaseModel):
    title: str
    blocks: list[dict[str, object]]

class NotePatchRequest(BaseModel):
    title: str | None = None
    blocks: list[dict[str, object]] | None = None

class NoteBlockRequest(BaseModel):
    block_kind: str = "text"
    content: str

class NoteBlocksRequest(BaseModel):
    blocks: list[dict[str, object]]

class NoteGenerationRequest(BaseModel):
    topic: str
    material_id: str
    source_revision: str | None = None
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True

class NoteSourceRefreshRequest(BaseModel):
    note_id: str | None = None
    material_id: str | None = None

class PracticeSessionRequest(BaseModel):
    title: str
    exercise_ids: list[str]
    duration_seconds: int = 600
    timezone: str = "UTC"
    local_date: str = "1970-01-01"

class PracticeSubmitRequest(BaseModel):
    answer: object

class PracticeRecommendationQuery(BaseModel):
    limit: int = 10
    weak_point: str | None = None

class AttemptReviewRequest(BaseModel):
    decision: str
    feedback: str = ""

class MistakeFeedbackRequest(BaseModel):
    event_kind: str
    content: str = ""

class MistakeMarkRequest(BaseModel):
    feedback: str = ""

class CramGoalRequest(BaseModel):
    title: str
    target_date: str
    timezone: str = "UTC"
    target_exercise_count: int = 1
    plan_id: str | None = None
    plan_item_id: str | None = None

class CramSessionRequest(BaseModel):
    title: str
    exercise_ids: list[str]
    duration_seconds: int = 600
    timezone: str = "UTC"
    local_date: str = "1970-01-01"

class CaptureSessionRequest(BaseModel):
    asset_kind: str
    original_name: str
    media_type: str

class TranscriptEditRequest(BaseModel):
    draft_id: str
    text: str

class TranscriptActionRequest(BaseModel):
    draft_id: str

class ReportRequest(BaseModel):
    report_kind: str
    timezone: str
    period_start: str
    period_end: str

class DeliveryRequest(BaseModel):
    channel: str
    target_label: str
    mode: str | None = None
    authorization_granted: bool = False
    retry_of: str | None = None

