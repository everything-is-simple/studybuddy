from pathlib import Path


PLANS = (Path(__file__).parents[1] / "app" / "static" / "plans.html").read_text(encoding="utf-8")


def test_plan_selection_and_mutation_have_independent_generations():
    assert "selectionGeneration=0,mutationGeneration=0" in PLANS
    assert "const mutationRun=++mutationGeneration;setBusy(true)" in PLANS
    assert "const selectionRun=++selectionGeneration,mutationRun=mutationGeneration" in PLANS


def test_late_selection_cannot_write_plan_status_after_mutation():
    assert "if(plan.id!==selected||detail.hidden)selectPlan(plan.id)" in PLANS
    assert "selectionRun===selectionGeneration&&mutationRun===mutationGeneration" in PLANS
    assert "setStatus('计划已加载')" in PLANS
    assert "if(mutationRun===mutationGeneration)setStatus(success,'status-ready')" in PLANS
