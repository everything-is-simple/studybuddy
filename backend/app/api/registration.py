"""API 路由注册模块。

按照固定的遗留顺序注册所有 API 路由组。

注册顺序很重要：后注册的模块可以访问先注册模块定义的辅助函数和常量。
这种设计允许模块间共享上下文，但也创建了隐式依赖关系。

路由注册顺序（不可更改）：
1. system - 系统健康检查
2. materials_collection - 材料列表和搜索
3. ai_retrieval_qa - AI 检索与问答
4. ai_indexing - AI 索引管理
5. tasks - 异步任务管理
6. study_generation - 学习内容生成
7. study_practice - 练习与测试
8. study_plans - 学习计划
9. study_rhythm - 学习节奏
10. study_notes - 笔记管理
11. study_learning - 学习/卡片管理
12. study_capture_reports - 学习捕获与报告
13. materials_detail - 材料详情和导出
14. web - 前端路由
"""

from . import system
from . import materials_collection
from . import ai_retrieval_qa
from . import ai_indexing
from . import tasks
from . import study_generation
from . import study_practice
from . import study_plans
from . import study_rhythm
from . import study_notes
from . import study_learning
from . import study_capture_reports
from . import materials_detail
from . import web


ROUTE_MODULES = (system, materials_collection, ai_retrieval_qa, ai_indexing, tasks, study_generation, study_practice, study_plans, study_rhythm, study_notes, study_learning, study_capture_reports, materials_detail, web,)


def register_all_routes(app, context: dict[str, object]) -> None:
    """按顺序注册所有 API 路由组。
    
    每个路由模块通过 `register_routes(app, context)` 函数注册自己的路由，
    并可以向 context 添加新的辅助函数供后续模块使用。
    
    Args:
        app: FastAPI 应用实例
        context: 初始上下文字典，包含共享的辅助函数和常量
                 （如 connect, HTTPException 等）
    
    Side Effects:
        - 在 app 上注册所有 HTTP 端点
        - 累积更新 context，后续模块可访问前面模块定义的辅助函数
        
    Note:
        路由注册顺序是固定的（ROUTE_MODULES 元组），不可更改。
        后注册的模块可以访问先注册模块的辅助函数，这创建了隐式依赖。
    """
    for module in ROUTE_MODULES:
        context = module.register_routes(app, context)
        # Later route groups retain access to helpers defined by earlier groups.
        context.update({
            name: value for name, value in module.__dict__.items()
            if not name.startswith("__") and name != "register_routes"
        })
