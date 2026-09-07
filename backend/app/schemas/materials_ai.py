"""材料和 AI 功能的请求模式定义。

本模块包含 StudyBuddy 核心功能的请求数据模型：
- 材料管理：重命名、导出
- AI 检索：语义搜索、上下文获取、引用验证
- AI 问答：基于材料的问答生成
- 学习卡片：卡组、卡片创建和复习
- 练习题：题集、题目创建和答题
- AI 生成：卡片和练习题的自动生成
- 学习计划：目标、模块、计划、依赖、进度

所有模型基于 Pydantic BaseModel，提供自动类型验证。
"""

from __future__ import annotations

from pydantic import BaseModel

class RenameMaterialRequest(BaseModel):
    """材料重命名请求。
    
    Attributes:
        original_name: 新的文件名（包含扩展名）
    """
    original_name: str

class ExportMaterialsRequest(BaseModel):
    """材料导出请求。
    
    Attributes:
        material_ids: 要导出的材料 ID 列表
        include_original: 是否包含原始文件（默认 True）
        include_text: 是否包含提取的文本（默认 True）
    """
    material_ids: list[str]
    include_original: bool = True
    include_text: bool = True

class RetrievalRequest(BaseModel):
    """检索请求。
    
    Attributes:
        query: 检索查询字符串
        material_ids: 限制检索范围的材料 ID 列表（可选）
        top_k: 返回前 K 个结果（默认 5）
        mode: 检索模式（"lexical" 或 "semantic"，默认 "lexical"）
        allow_fallback: 当语义检索失败时是否降级到词法检索（默认 True）
    """
    query: str
    material_ids: list[str] | None = None
    top_k: int = 5
    mode: str = "lexical"
    allow_fallback: bool = True

class ContextRequest(BaseModel):
    """上下文获取请求。
    
    Attributes:
        hit_ids: 检索命中的 chunk ID 列表
        max_tokens: 最大 token 数（默认 2000）
    """
    hit_ids: list[str]
    max_tokens: int = 2000

class CitationValidateRequest(BaseModel):
    """引用验证请求。
    
    Attributes:
        key: 引用键（格式为 "ctx-xxx"）
    """
    key: str

class QaAskRequest(BaseModel):
    """AI 问答请求。
    
    Attributes:
        question: 用户问题
        material_ids: 作为上下文的材料 ID 列表
        thread_id: 会话线程 ID（可选，用于多轮对话）
        top_k: 检索前 K 个相关块（默认 5）
        retrieval_mode: 检索模式（"lexical" 或 "semantic"）
        allow_retrieval_fallback: 是否允许检索降级（默认 True）
    """
    question: str
    material_ids: list[str]
    thread_id: str | None = None
    top_k: int = 5
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True

class DeckRequest(BaseModel):
    """卡组创建请求。
    
    Attributes:
        title: 卡组标题
        description: 卡组描述（默认空）
    """
    title: str
    description: str = ""

class CardRequest(BaseModel):
    """学习卡片创建请求。
    
    Attributes:
        front: 卡片正面内容
        back: 卡片背面内容
        explanation: 补充解释（默认空）
        tags: 标签列表（默认空）
        citations: 引用列表（默认空）
        card_type: 卡片类型（"user_created" 或 "ai_generated"）
        source_revision: 源修订版本（可选）
    """
    front: str
    back: str
    explanation: str = ""
    tags: list[str] = []
    citations: list[dict[str, object]] = []
    card_type: str = "user_created"
    source_revision: str | None = None

class CardReviewRequest(BaseModel):
    """卡片复习记录请求。
    
    Attributes:
        result: 复习结果（"again", "hard", "good", "easy"）
    """
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

