"""Eval de convergence : l'agent prend-il le chemin le plus court pour une même question ?

Même principe que evaluating-ai-agents/evals/convergence.py : la même question formulée de
15 façons, on compte les étapes de chaque exécution (décisions de l'agent = appels d'outils
+ la réponse), puis on note chaque exécution par rapport à la plus courte.

Différence assumée : seule une exécution à la réponse CORRECTE (juge FinanceBench) peut
servir de chemin optimal, et une réponse fausse vaut 0. Sinon un agent qui répond faux
sans chercher aurait le « meilleur » chemin.

    uv run python backend/evals/convergence.py              # 15 formulations, ~0,50 $
    uv run python backend/evals/convergence.py --reps 3     # chaque formulation 3 fois

Résultat : une expérience LangSmith « Convergence » sur le dataset « FinanceBench —
convergence », avec par exécution les feedbacks `correct` et `convergence` (0 à 1).
"""
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Question FinanceBench où l'agent cherche (2 appels d'outils au dernier run) et réussit :
# un calcul sur le bilan, la page de preuve n'est pas toujours dans le retrieval initial.
QUESTION_ID = "financebench_id_00222"
DATASET_NAME = "agentic-search · FinanceBench — convergence"

# Même question (quick ratio d'AMD en FY22), formulée différemment
CONVERGENCE_QUESTIONS = [
    ("Does AMD have a reasonably healthy liquidity profile based on its quick ratio for FY22? "
     "If the quick ratio is not relevant to measure liquidity, please state that and explain why."),
    "What was AMD's quick ratio for fiscal year 2022, and does it indicate healthy liquidity?",
    "Based on the quick ratio, is AMD's liquidity healthy as of FY2022?",
    "Compute AMD's FY22 quick ratio and say whether its liquidity looks sound.",
    "Is AMD's short-term liquidity healthy in 2022, judging by its acid-test ratio?",
    "How liquid was AMD at the end of FY2022 according to its quick ratio?",
    "Calculate the quick ratio of AMD for 2022. Is that a healthy level of liquidity?",
    "Using the FY22 balance sheet, what is AMD's quick ratio and what does it say about liquidity?",
    "Does AMD's acid-test ratio for fiscal 2022 point to a healthy liquidity position?",
    "Can AMD cover its current liabilities with its quick assets as of FY2022?",
    "What does AMD's 2022 quick ratio tell us about the health of its liquidity?",
    "Evaluate AMD's liquidity in FY22 using the quick ratio.",
    "For fiscal year 2022, is AMD's quick ratio above 1, and is its liquidity healthy?",
    "Give AMD's quick ratio at fiscal year-end 2022 and assess its liquidity profile.",
    "Is the liquidity of AMD healthy in FY2022 when measured with the quick ratio?",
]


def steps_of(tool_calls: int) -> int:
    """Décisions de l'agent : chaque appel d'outil, plus la réponse finale."""
    return int(tool_calls or 0) + 1


def optimal_steps(outputs: List[Dict]) -> Optional[int]:
    """Chemin le plus court parmi les exécutions à la réponse correcte (None si aucune)."""
    steps = [o["steps"] for o in outputs if o.get("verdict") == "CORRECT" and o.get("steps")]
    return min(steps) if steps else None


def convergence_score(outputs: Dict, optimal: Optional[int]) -> float:
    """1.0 = bonne réponse par le chemin le plus court ; plus bas = étapes en trop ; 0 = faux."""
    if optimal is None or outputs.get("verdict") != "CORRECT" or not outputs.get("steps"):
        return 0.0
    return optimal / float(outputs["steps"])


def _example(rows: List[Dict]) -> Dict:
    for example in rows:
        if example["id"] == QUESTION_ID:
            return example
    raise SystemExit(f"{QUESTION_ID} absent du dataset FinanceBench : lancer d'abord backend/evals/financebench/prepare.py")


def _get_or_create_dataset(client, expected_answer: str):
    if client.has_dataset(dataset_name=DATASET_NAME):
        return client.read_dataset(dataset_name=DATASET_NAME)
    dataset = client.create_dataset(
        DATASET_NAME, description=f"La question {QUESTION_ID} de FinanceBench, formulée de 15 façons.",
    )
    client.create_examples(
        dataset_id=dataset.id,
        inputs=[{"question": q} for q in CONVERGENCE_QUESTIONS],
        outputs=[{"answer": expected_answer} for _ in CONVERGENCE_QUESTIONS],
    )
    return dataset


def run_convergence_eval(reps: int = 1) -> int:
    from langsmith import Client

    from backend.agents.workflow import AgentState, AgentWorkflow, effective_top_k
    from backend.config.settings import settings
    from backend.evals.experiment_utils import FinanceBenchJudge, call_with_backoff, eval_index, traced_in_project
    from backend.evals.financebench.langsmith_sync import load_rows

    if not settings.LANGSMITH_API_KEY:
        print("✗ LANGSMITH_API_KEY absente : l'expérience ne serait enregistrée nulle part.", file=sys.stderr)
        return 1
    client = Client(api_key=settings.LANGSMITH_API_KEY)
    rows = load_rows(client)  # dataset « FinanceBench » de LangSmith
    example = _example(rows)
    dataset = _get_or_create_dataset(client, example["expected_answer"])

    # Même index (combiné, collections d'éval de Qdrant) et mêmes agents que le mode agentic
    # du runner FinanceBench : la recherche porte sur les 4 rapports, pas sur le seul bon.
    docs = sorted({ex["doc_name"] for ex in rows})
    retriever, page_store = eval_index(docs)
    workflow = AgentWorkflow()
    judge = FinanceBenchJudge()

    def run_agent_and_track_path(inputs: dict) -> dict:
        """Tâche de l'expérience : lance l'agent, compte ses étapes, juge la réponse."""
        question = inputs["question"]
        docs = retriever.invoke(question)
        state = AgentState(question=question, documents=docs, draft_answer="", verification_report="",
                           is_relevant=False, retriever=retriever, page_store=page_store,
                           corrective_rounds=0, tool_calls=0)
        final = call_with_backoff(lambda: workflow.compiled_workflow.invoke(state), "convergence", log=print)
        seen = (final.get("documents") or docs)[:effective_top_k(final)]
        verdict = call_with_backoff(lambda: judge.evaluate(
            question=example["question"], expected_answer=example["expected_answer"],
            generated_answer=final["draft_answer"],
            context="\n\n".join(d.page_content for d in seen),
            justification=example.get("justification", ""),
        ), "juge", log=print)
        return {
            "answer": final["draft_answer"],
            "tool_calls": final.get("tool_calls", 0),
            "steps": steps_of(final.get("tool_calls", 0)),
            "tool_queries": final.get("corrective_queries", []),
            "verdict": verdict.verdict,
        }

    def correct(outputs: dict) -> dict:
        return {"key": "correct", "score": 1.0 if outputs.get("verdict") == "CORRECT" else 0.0}

    # 1) On lance l'expérience, avec le verdict du juge
    results = client.evaluate(
        run_agent_and_track_path,
        data=dataset.name,
        evaluators=[traced_in_project(correct)],
        disable_evaluator_tracing=True,  # tracés dans agentic-search (tag « evaluator »), pas dans « evaluators »
        experiment_prefix="Convergence",
        description=f"Convergence sur {QUESTION_ID}, {len(CONVERGENCE_QUESTIONS)} formulations × {reps}",
        num_repetitions=reps,
        max_concurrency=2,
        metadata={"question_id": QUESTION_ID, "reasoning_model": settings.REASONING_MODEL_ID},
    )

    # 2) Le score dépend de toutes les exécutions : on calcule le chemin optimal…
    outputs = [row["run"].outputs for row in results if row["run"].outputs]
    optimal = optimal_steps(outputs)
    if optimal is None:
        print("Aucune réponse correcte : convergence = 0 sur toute l'expérience")
    else:
        print(f"Chemin optimal : {optimal} étape(s)")

    def convergence(outputs: dict) -> dict:
        return {"key": "convergence", "score": convergence_score(outputs, optimal)}

    # 3) … puis on ajoute l'évaluateur à l'expérience existante
    client.evaluate(results.experiment_name, evaluators=[traced_in_project(convergence)],
                    disable_evaluator_tracing=True)

    scores = [convergence_score(o, optimal) for o in outputs]
    n_correct = sum(o.get("verdict") == "CORRECT" for o in outputs)
    print(f"✓ Expérience « {results.experiment_name} » : {len(outputs)} exécutions, "
          f"{n_correct} correctes, convergence moyenne {sum(scores) / max(len(scores), 1):.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval de convergence de l'agent (LangSmith)")
    parser.add_argument("--reps", type=int, default=1, help="exécutions par formulation")
    args = parser.parse_args()
    return run_convergence_eval(args.reps)


if __name__ == "__main__":
    sys.exit(main())
