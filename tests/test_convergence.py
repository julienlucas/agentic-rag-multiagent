"""Eval de convergence : chemin optimal et scores, sans appel de modèle."""
from evaluation.convergence import (
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


def test_fifteen_distinct_formulations_of_a_real_financebench_question():
    assert len(CONVERGENCE_QUESTIONS) == 15
    assert len(set(CONVERGENCE_QUESTIONS)) == 15
    example = _example()
    assert example["id"] == QUESTION_ID
    assert CONVERGENCE_QUESTIONS[0] == example["question"]  # la formulation d'origine en premier
