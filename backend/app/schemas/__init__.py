"""Schema 数据模型模块。

本模块提供整个 StudyBuddy 系统的 Pydantic 数据模型定义，用于：
- 配置文件的加载和验证（LocalSettings, ConnectionTest）
- 材料和 AI 功能的数据结构（材料元数据、向量索引、检索结果）
- 学习功能的数据结构（笔记、练习、计划、节奏）

主要模块：
- materials_ai: 材料、向量、检索、问答相关的数据模型
- study: 学习、练习、计划、节奏相关的数据模型
- local_settings: 本地配置文件模型（data_root, providers）
- connection_test: 数据库连接测试结果模型

所有模型都基于 Pydantic BaseModel，提供自动类型验证和序列化。
"""

from .materials_ai import *
from .study import *
