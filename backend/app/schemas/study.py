"""学习功能的请求模式定义。

本模块包含 StudyBuddy 学习相关功能的请求数据模型：
- 源链接：学习内容与材料的关联
- 节奏管理：学习计划、时间分配
- 笔记：创建和编辑结构化笔记
- 错题本：错误标记和反馈
- 集中模式：目标和会话管理
- 采集与转录：音频/图像采集和编辑
- 报告与发送：学习报告生成和邮件发送

所有模型基于 Pydantic BaseModel，提供自动类型验证。
"""

from __future__ import annotations

from pydantic import BaseModel

class StudySourceLinkRequest(BaseModel):
    """学习源链接请求。
    
    Attributes:
        material_id: 材料 ID
        revision_id: 修订版本 ID
        extraction_id: 提取 ID（可选）
        chunk_id: 块 ID
        span_id: 片段 ID（可选）
        citation_key: 引用键（可选）
    """
    material_id: str
    revision_id: str
    extraction_id: str | None = None
    chunk_id: str
    span_id: str | None = None
    citation_key: str | None = None

class NoteSourceLinkRequest(BaseModel):
    """笔记源链接请求。
    
    Attributes:
        material_id: 材料 ID
        revision_id: 修订版本 ID
        extraction_id: 提取 ID
        chunk_id: 块 ID
        span_id: 片段 ID（可选）
        citation_key: 引用键
        context_chunk_ids: 上下文块 ID 列表
    """
    material_id: str
    revision_id: str
    extraction_id: str
    chunk_id: str
    span_id: str | None = None
    citation_key: str
    context_chunk_ids: list[str]

class RhythmSettingsRequest(BaseModel):
    """节奏设置请求。
    
    Attributes:
        cadence: 节奏类型（"daily", "weekly", "monthly"）
        timezone: 时区（如 "Asia/Shanghai"）
        period_start: 周期开始日期
        target_minutes: 目标学习时长（分钟）
    """
    cadence: str
    timezone: str
    period_start: str
    target_minutes: int

class RhythmAllocationRequest(BaseModel):
    """节奏分配请求。
    
    Attributes:
        item_id: 计划项 ID
        local_date: 本地日期（ISO 格式）
        planned_minutes: 计划学习时长（分钟）
    """
    item_id: str
    local_date: str
    planned_minutes: int

class RhythmAllocationPatchRequest(BaseModel):
    local_date: str | None = None
    planned_minutes: int | None = None

class NoteRequest(BaseModel):
    """笔记创建请求。
    
    Attributes:
        title: 笔记标题
        blocks: 笔记块列表（结构化 JSON）
    """
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
    """错误标记请求。
    
    Attributes:
        feedback: 反馈内容（默认空）
    """
    feedback: str = ""

class CramGoalRequest(BaseModel):
    """集中学习目标请求。
    
    Attributes:
        title: 目标标题
        target_date: 目标日期
        timezone: 时区（默认 "UTC"）
        target_exercise_count: 目标题数（默认 1）
        plan_id: 关联计划 ID（可选）
        plan_item_id: 关联计划项 ID（可选）
    """
    title: str
    target_date: str
    timezone: str = "UTC"
    target_exercise_count: int = 1
    plan_id: str | None = None
    plan_item_id: str | None = None

class CramSessionRequest(BaseModel):
    """集中学习会话请求。
    
    Attributes:
        title: 会话标题
        exercise_ids: 练习题 ID 列表
        duration_seconds: 会话时长（秒，默认 600）
        timezone: 时区（默认 "UTC"）
        local_date: 本地日期（默认 "1970-01-01"）
    """
    title: str
    exercise_ids: list[str]
    duration_seconds: int = 600
    timezone: str = "UTC"
    local_date: str = "1970-01-01"

class CaptureSessionRequest(BaseModel):
    """采集会话请求。
    
    Attributes:
        asset_kind: 资产类型（"audio" 或 "image"）
        original_name: 原始文件名
        media_type: MIME 类型
    """
    asset_kind: str
    original_name: str
    media_type: str

class TranscriptEditRequest(BaseModel):
    """转录编辑请求。
    
    Attributes:
        draft_id: 草稿 ID
        text: 编辑后的文本
    """
    draft_id: str
    text: str

class TranscriptActionRequest(BaseModel):
    draft_id: str

class ReportRequest(BaseModel):
    """报告生成请求。
    
    Attributes:
        report_kind: 报告类型（"weekly", "monthly"）
        timezone: 时区
        period_start: 周期开始日期
        period_end: 周期结束日期
    """
    report_kind: str
    timezone: str
    period_start: str
    period_end: str

class DeliveryRequest(BaseModel):
    """报告发送请求。
    
    Attributes:
        channel: 发送渠道（"smtp" 或 "feishu"）
        target_label: 目标标签
        mode: 发送模式（可选）
        authorization_granted: 是否授权（默认 False）
        retry_of: 重试的原请求 ID（可选）
    """
    channel: str
    target_label: str
    mode: str | None = None
    authorization_granted: bool = False
    retry_of: str | None = None

