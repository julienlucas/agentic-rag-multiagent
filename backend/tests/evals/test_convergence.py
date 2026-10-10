"""Eval de convergence : chemin optimal et scores, sans appel de modèle."""
import json

from backend.evals.convergence import (
    CONVERGENCE_QUESTIONS,
    QUESTION_ID,
    _example,
    convergence_score,
    optimal_steps,
    steps_of,
)


def test_steps_count_each_tool_call_plus_the_answer():
    assert steps_of(0) == 1
    assert steps_of(2) == 3
    assert steps_of(None) == 1


def test_optimal_path_is_the_shortest_correct_run():
    outputs = [
        {"steps": 1, "verdict": "INCORRECT"},  # répond faux sans chercher : pas un modèle à suivre
        {"steps": 3, "verdict": "CORRECT"},
        {"steps": 2, "verdict": "CORRECT"},
    ]
    assert optimal_steps(outputs) == 2


def test_no_correct_run_means_no_optimal_path():
    assert optimal_steps([{"steps": 1, "verdict": "INCORRECT"}]) is None
    assert convergence_score({"steps": 1, "verdict": "CORRECT"}, None) == 0.0


def test_scores_reward_the_shortest_correct_path():
    assert convergence_score({"steps": 2, "verdict": "CORRECT"}, 2) == 1.0
    assert convergence_score({"steps": 4, "verdict": "CORRECT"}, 2) == 0.5
    assert convergence_score({"steps": 1, "verdict": "INCORRECT"}, 2) == 0.0  # faux = 0, même court


def test_fifteen_distinct_formulations_of_a_protocol_question():
    from backend.evals.financebench.regression import BASELINE_PATH
    assert len(CONVERGENCE_QUESTIONS) == 15
    assert len(set(CONVERGENCE_QUESTIONS)) == 15
    # La question fait partie du protocole (dataset LangSmith « FinanceBench », reflété par la baseline).
    assert QUESTION_ID in json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["questions"]


def test_example_is_picked_from_the_langsmith_rows():
    rows = [{"id": "autre", "question": "x"}, {"id": QUESTION_ID, "question": CONVERGENCE_QUESTIONS[0]}]
    assert _example(rows)["question"] == CONVERGENCE_QUESTIONS[0]


def test_evaluators_are_traced_in_the_app_project_with_a_tag(monkeypatch):
    """Comme evaluating-ai-agents : pas de projet « evaluators », un tag dans agentic-search.
    On contrôle la configuration du traçage, sans rien envoyer à LangSmith."""
    import langsmith

    from backend.evals.experiment_utils import EVALUATOR_TAG, traced_in_project

    seen = {}

    def fake_traceable(**config):
        seen.update(config)
        return lambda fn: fn

    monkeypatch.setattr(langsmith, "traceable", fake_traceable)

    def correct(outputs: dict) -> dict:
        return {"key": "correct", "score": 1.0}

    assert traced_in_project(correct)({"verdict": "CORRECT"}) == {"key": "correct", "score": 1.0}
    assert seen["project_name"] == "agentic-search"
    assert seen["tags"] == [EVALUATOR_TAG]
    assert seen["name"] == "correct"
