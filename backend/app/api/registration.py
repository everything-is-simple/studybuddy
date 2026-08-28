"""Register API route groups in the frozen legacy order."""

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
    for module in ROUTE_MODULES:
        context = module.register_routes(app, context)
        # Later route groups retain access to helpers defined by earlier groups.
        context.update({
            name: value for name, value in module.__dict__.items()
            if not name.startswith("__") and name != "register_routes"
        })
