from __future__ import annotations

from pydantic import BaseModel

class RenameMaterialRequest(BaseModel):
    original_name: str

class ExportMaterialsRequest(BaseModel):
    material_ids: list[str]
    include_original: bool = True
    include_text: bool = True

class RetrievalRequest(BaseModel):
    query: str
    material_ids: list[str] | None = None
    top_k: int = 5
    mode: str = "lexical"
    allow_fallback: bool = True

class ContextRequest(BaseModel):
    hit_ids: list[str]
    max_tokens: int = 2000

class CitationValidateRequest(BaseModel):
    key: str

class QaAskRequest(BaseModel):
    question: str
    material_ids: list[str]
    thread_id: str | None = None
    top_k: int = 5
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True

class DeckRequest(BaseModel):
    title: str
    description: str = ""

class CardRequest(BaseModel):
    front: str
    back: str
    explanation: str = ""
    tags: list[str] = []
    citations: list[dict[str, object]] = []
    card_type: str = "user_created"
    source_revision: str | None = None

class CardReviewRequest(BaseModel):
    result: str

class ExerciseSetRequest(BaseModel):
    title: str
    description: str = ""

class ExerciseRequest(BaseModel):
    exercise_type: str
    prompt: str
    options: list[str] = []
    answer_key: object
    explanation: str = ""
    citations: list[dict[str, object]] = []
    exercise_kind: str = "user_created"
    source_revision: str | None = None

class ExerciseAttemptRequest(BaseModel):
    answer: object

class ExerciseUpdateRequest(BaseModel):
    prompt: str
    options: list[str] = []
    # The ordinary study UI never receives an answer key.  Omission preserves
    # the internal key for draft-only wording/explanation edits.
    answer_key: object | None = None
    explanation: str = ""
    citations: list[dict[str, object]] = []

class GenerationRequest(BaseModel):
    topic: str
    material_ids: list[str]
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True
    count: int = 1
    exercise_type: str | None = None
    source_revision: str | None = None

class StudyGoalRequest(BaseModel):
    title: str
    description: str = ""

class StudyModuleRequest(BaseModel):
    title: str
    description: str = ""

class StudyPlanRequest(BaseModel):
    goal_id: str
    title: str
    description: str = ""

class StudyPlanPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None

class StudyPlanItemRequest(BaseModel):
    title: str
    description: str = ""
    position: int | None = None
    module_id: str | None = None
    deck_id: str | None = None
    exercise_set_id: str | None = None

class StudyPlanItemPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    position: int | None = None
    module_id: str | None = None
    deck_id: str | None = None
    exercise_set_id: str | None = None

class StudyDependencyRequest(BaseModel):
    predecessor_item_id: str
    successor_item_id: str

class StudyProgressRequest(BaseModel):
    event_type: str
    metadata: dict[str, object] = {}
    event_id: str | None = None

