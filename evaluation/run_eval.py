# Évalue retrieval + QA sur le jeu interne (2 documents, questions en français) :
# Recall@k/MRR/nDCG, F1, verdicts du juge, régressions.
#
# Ce jeu ne remplace pas FinanceBench : sa vérité terrain est rédigée à la main, il ne
# vaut donc rien comme score de performance publiable. Il sert à vérifier que le pipeline
# tient hors du domaine financier et en français — la seule couverture de ce genre ici.
#
# Usage :
#   uv run python evaluation/run_eval.py --mode both
#   uv run python evaluation/run_eval.py --max-items 3 --no-judge --out-dir /tmp/eval-essai

import argparse
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.agents.workflow import AgentState, AgentWorkflow
from backend.agents.research_agent import ResearchAgent
from evaluation.utils import (
    build_retriever_for_file,
    call_with_backoff,
    is_rate_limit,
    load_dataset,
    log_to_langsmith,
    resolve_file_path,
    root_cause,
)
from evaluation.llm_judge import (
    FinanceBenchJudge,
    FinanceBenchVerdict,
    LLMJudge,
    aggregate_financebench_verdicts,
)
from backend.config.settings import settings

# stdout réel, conservé avant que le pipeline (très bavard) ne soit mis en sourdine :
# avec plusieurs workers, ses DEBUG rendent la sortie illisible.
_REAL_STDOUT = sys.stdout
_PRINT_LOCK = threading.Lock()


def _log(msg: str):
    with _PRINT_LOCK:
        print(f"[eval] {msg}", file=_REAL_STDOUT, flush=True)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> List[str]:
    return _normalize(text).split()


def _f1_score(pred: str, ref: str) -> float:
    pred_toks = _tokens(pred)
    ref_toks = _tokens(ref)
    if not pred_toks or not ref_toks:
        return 0.0
    common = {}
    for tok in pred_toks:
        common[tok] = common.get(tok, 0) + 1
    overlap = 0
    for tok in ref_toks:
        if common.get(tok, 0) > 0:
            overlap += 1
            common[tok] -= 1
    precision = overlap / max(len(pred_toks), 1)
    recall = overlap / max(len(ref_toks), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _context_hits(docs, expected_answer: str, keywords: Optional[List[str]]) -> bool:
    context = "\n\n".join(getattr(d, "page_content", "") for d in docs)
    if expected_answer:
        if _normalize(expected_answer) in _normalize(context):
            return True
    if keywords:
        norm_ctx = _normalize(context)
        return any(_normalize(k) in norm_ctx for k in keywords if k)
    return False


def _normalize_list(values: Optional[List[str]]) -> List[str]:
    return [_normalize(v) for v in (values or []) if v]


def _token_overlap_score(gold_text: str, doc_text: str) -> float:
    """Calcule le ratio de tokens du gold présents dans le doc."""
    gold_toks = _tokens(gold_text)
    if not gold_toks:
        return 0.0
    doc_toks_set = set(_tokens(doc_text))
    matched = sum(1 for t in gold_toks if t in doc_toks_set)
    return matched / len(gold_toks)


def _doc_relevance_flags(docs, gold_passages: Optional[List[str]], fuzzy_threshold: float = 0.6) -> List[int]:
    """
    Détermine la pertinence de chaque doc par rapport aux gold passages.
    Utilise un matching hybride : substring exact OU token overlap >= seuil.
    """
    if not gold_passages:
        return []
    gold = _normalize_list(gold_passages)
    flags = []
    for doc in docs:
        content = _normalize(getattr(doc, "page_content", ""))
        # Match exact (substring) — rapide
        if any(g in content for g in gold):
            flags.append(1)
            continue
        # Match fuzzy (token overlap) — rattrape les reformulations et coupures
        if any(_token_overlap_score(g, content) >= fuzzy_threshold for g in gold):
            flags.append(1)
            continue
        flags.append(0)
    return flags


def _recall_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    total_relevant = sum(flags)
    if total_relevant == 0:
        return 0.0
    return min(sum(flags[:k]) / total_relevant, 1.0)


def _mrr_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    for idx, rel in enumerate(flags[:k], start=1):
        if rel:
            return 1.0 / idx
    return 0.0


def _ndcg_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    dcg = 0.0
    for i, rel in enumerate(flags[:k], start=1):
        if rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal = sorted(flags, reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal[:k], start=1):
        if rel:
            idcg += 1.0 / math.log2(i + 1)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _parse_section_header(line: str) -> Optional[str]:
    """Extrait le nom de section depuis une ligne `# Factual (8)` / `# Multi-passage (2)`."""
    line = line.strip()
    if not line.startswith("#"):
        return None
    m = re.match(r"^\s*#\s*(.+?)\s*\(\d+\)\s*$", line)
    if m:
        return m.group(1).strip()
    return None


def _example_labels_for_dataset(path: str) -> List[str]:
    """Une étiquette par ligne JSON, alignée sur load_dataset (ex. « Factual 3 », « Numerical 2 »)."""
    labels: List[str] = []
    current_category = ""
    idx_in_section = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            cat = _parse_section_header(line)
            if cat is not None:
                current_category = cat
                idx_in_section = 0
                continue
            if line.startswith("#"):
                continue
            json.loads(line)
            idx_in_section += 1
            if current_category:
                labels.append(f"{current_category} {idx_in_section}")
            else:
                labels.append(f"Example {idx_in_section}")
    return labels


def _parse_verification_flags(report: str) -> Tuple[Optional[bool], Optional[bool], Optional[bool]]:
    supported = None
    relevant = None
    has_unsupported = None
    for line in (report or "").splitlines():
        line = line.strip().lower()
        if line.startswith("**supporté:**"):
            supported = "oui" in line
        if line.startswith("**pertinent:**"):
            relevant = "oui" in line
        if line.startswith("**affirmations non supportées:**"):
            has_unsupported = "aucune" not in line and "[]" not in line
    return supported, relevant, has_unsupported


def evaluate_example(
    example: Dict,
    retriever,
    modes: List[str],
    workflow: Optional[AgentWorkflow],
    researcher: Optional[ResearchAgent],
    judge,
    k_values: List[int],
) -> List[Dict]:
    """
    Récupère une seule fois, puis génère une réponse par mode évalué.

    Le retrieval était refait pour chaque mode, et le mode agentic le refaisait une
    troisième fois via full_pipeline() : trois recherches là où une suffit, pour des
    documents identiques. Les métriques de retrieval sont donc calculées une fois et
    partagées, comme dans le harness FinanceBench.
    """
    question = example["question"].strip()
    expected_answer = example.get("expected_answer", "").strip()
    keywords = example.get("answer_keywords", [])
    gold_passages = example.get("gold_passages", [])

    t0 = time.time()
    docs = retriever.invoke(question)
    retrieval_sec = time.time() - t0

    flags = _doc_relevance_flags(docs, gold_passages)
    retrieval_metrics = {"retrieval_sec": round(retrieval_sec, 2), "n_docs": len(docs)}
    for k in k_values:
        retrieval_metrics[f"recall@{k}"] = _recall_at_k(flags, k)
        retrieval_metrics[f"mrr@{k}"] = _mrr_at_k(flags, k)
        retrieval_metrics[f"ndcg@{k}"] = _ndcg_at_k(flags, k)

    top_k = settings.RESEARCH_TOP_K
    rows = []
    for mode in modes:
        result = {
            "id": example.get("id"),
            "file_name": example.get("file_name"),
            "question": question,
            "expected_answer": expected_answer,
            "mode": mode,
            **retrieval_metrics,
        }
        supported = relevant = has_unsupported = None

        # Chaque mode est isolé : l'échec de l'un ne doit pas retirer silencieusement
        # la question de l'échantillon et fausser le dénominateur.
        t1 = time.time()
        try:
            if mode == "baseline":
                answer = call_with_backoff(
                    lambda: researcher.generate(question, docs[:top_k])["draft_answer"],
                    f"la génération baseline ({example.get('id')})", log=_log,
                )
                llm_docs = docs[:top_k]
            else:
                # Graphe compilé invoqué directement avec les documents déjà récupérés :
                # full_pipeline() relancerait un retrieval complet.
                state = AgentState(
                    question=question,
                    documents=docs,
                    draft_answer="",
                    verification_report="",
                    citations=[],
                    is_relevant=False,
                    retriever=retriever,
                    relevance="",
                    corrective_rounds=0,
                    corrective_queries=[],
                )
                final_state = call_with_backoff(
                    lambda: workflow.compiled_workflow.invoke(state),
                    f"la génération agentic ({example.get('id')})", log=_log,
                )
                answer = final_state["draft_answer"]
                supported, relevant, has_unsupported = _parse_verification_flags(
                    final_state.get("verification_report", "")
                )
                result["relevance"] = final_state.get("relevance", "")
                result["corrective_rounds"] = final_state.get("corrective_rounds", 0)
                # La recherche corrective a pu changer les documents : c'est ce qu'on mesure.
                llm_docs = (final_state.get("documents") or docs)[:top_k]
        except Exception as e:
            result.update({
                "failed": True,
                "error": root_cause(e),
                "rate_limited": is_rate_limit(e),
                "answer": "",
                "generation_sec": round(time.time() - t1, 2),
            })
            rows.append(result)
            continue

        result["answer"] = answer
        result["generation_sec"] = round(time.time() - t1, 2)
        result["context_hit"] = _context_hits(llm_docs, expected_answer, keywords)
        result["answer_f1"] = _f1_score(answer, expected_answer) if expected_answer else 0.0
        result["supported"] = supported
        result["relevant"] = relevant
        if mode == "agentic":
            # Ces deux signaux venaient du VerificationAgent, retiré en avril 2026 : le rapport
            # ne contient plus les lignes "**Supporté:**" / "**Affirmations non supportées:**".
            # Sans ce None, bool(None is False) valait False sur chaque question et le rapport
            # annonçait un « 0 % d'hallucinations » que rien n'avait mesuré. La métrique
            # d'hallucination vivante est celle du juge.
            if supported is None and has_unsupported is None:
                result["hallucinated"] = None
            else:
                result["hallucinated"] = bool((supported is False) or (has_unsupported is True))
        result["gold_passages"] = gold_passages

        if judge is not None and expected_answer:
            context = "\n\n".join(getattr(d, "page_content", "") for d in llm_docs)
            _judge_into(result, judge, question, expected_answer, answer, context)

        rows.append(result)

    return rows


def _judge_into(result: Dict, judge, question: str, expected: str, answer: str, context: str):
    """
    Écrit le verdict dans la ligne de résultat.

    Deux juges possibles : celui du protocole FinanceBench (1 appel LLM, verdict ternaire,
    comparable au second jeu d'éval) et l'historique à 3 axes (3 appels : correctness,
    faithfulness, completeness). Le premier est le défaut — trois appels par question et
    par mode, c'est ce qui faisait passer ce run de dix minutes à quatre-vingts.
    """
    try:
        if isinstance(judge, FinanceBenchJudge):
            verdict = call_with_backoff(
                lambda: judge.evaluate(
                    question=question,
                    expected_answer=expected,
                    generated_answer=answer,
                    context=context,
                ),
                f"le juge ({result.get('id')})", log=_log,
            )
            result["verdict"] = verdict.verdict
            result["judge_faithfulness"] = verdict.faithfulness
            result["judge_reason"] = verdict.reason
            result["judge_is_hallucination"] = verdict.is_hallucination
        else:
            judged = call_with_backoff(
                lambda: judge.evaluate(
                    question=question,
                    expected_answer=expected,
                    generated_answer=answer,
                    context=context,
                ),
                f"le juge ({result.get('id')})", log=_log,
            )
            result["judge_correctness"] = judged.correctness
            result["judge_faithfulness"] = judged.faithfulness
            result["judge_completeness"] = judged.completeness
            result["judge_correctness_reason"] = judged.correctness_reason
            result["judge_faithfulness_reason"] = judged.faithfulness_reason
            result["judge_completeness_reason"] = judged.completeness_reason
            result["judge_is_hallucination"] = judged.is_hallucination
    except Exception as e:
        # La réponse est valide, seul le juge a échoué : on garde la réponse.
        result["verdict"] = "ERROR"
        result["judge_reason"] = f"juge indisponible: {root_cause(e)}"


def aggregate(results: List[Dict], k_values: List[int]) -> Dict:
    if not results:
        return {}

    # Les questions en échec sortent du dénominateur mais restent comptées : un run
    # amputé de trois questions ne doit pas se lire comme un run complet.
    failed = [r for r in results if r.get("failed")]
    results = [r for r in results if not r.get("failed")]
    if not results:
        return {"count": 0, "failed": len(failed), "attempted": len(failed)}

    f1s = [r["answer_f1"] for r in results]
    hits = [r["context_hit"] for r in results]
    supported = [r["supported"] for r in results if r["supported"] is not None]
    relevant = [r["relevant"] for r in results if r["relevant"] is not None]
    hallucinated = [r["hallucinated"] for r in results if r.get("hallucinated") is not None]
    base = {
        "count": len(results),
        "failed": len(failed),
        "rate_limited": sum(1 for r in failed if r.get("rate_limited")),
        "attempted": len(results) + len(failed),
        "mean_generation_sec": round(mean(r["generation_sec"] for r in results), 2),
        "mean_retrieval_sec": round(mean(r["retrieval_sec"] for r in results), 2),
        "mean_f1": round(mean(f1s), 4),
        "context_hit_rate": round(sum(hits) / len(hits), 4),
        "supported_rate": round(sum(1 for v in supported if v) / len(supported), 4) if supported else None,
        "relevant_rate": round(sum(1 for v in relevant if v) / len(relevant), 4) if relevant else None,
        "hallucination_rate": round(sum(1 for v in hallucinated if v) / len(hallucinated), 4) if hallucinated else None,
    }
    retrieval = {}
    for k in k_values:
        recall_vals = [r.get(f"recall@{k}") for r in results if r.get(f"recall@{k}") is not None]
        mrr_vals = [r.get(f"mrr@{k}") for r in results if r.get(f"mrr@{k}") is not None]
        ndcg_vals = [r.get(f"ndcg@{k}") for r in results if r.get(f"ndcg@{k}") is not None]
        if recall_vals:
            retrieval[f"recall@{k}"] = round(mean(recall_vals), 4)
        if mrr_vals:
            retrieval[f"mrr@{k}"] = round(mean(mrr_vals), 4)
        if ndcg_vals:
            retrieval[f"ndcg@{k}"] = round(mean(ndcg_vals), 4)
    base["retrieval"] = retrieval

    # LLM Judge metrics
    judge_correctness = [r.get("judge_correctness") for r in results if r.get("judge_correctness") is not None]
    judge_faithfulness = [r.get("judge_faithfulness") for r in results if r.get("judge_faithfulness") is not None]
    judge_completeness = [r.get("judge_completeness") for r in results if r.get("judge_completeness") is not None]
    judge_hallucinations = [r.get("judge_is_hallucination") for r in results if r.get("judge_is_hallucination") is not None]

    verdicts = [r for r in results if r.get("verdict")]
    if verdicts:
        base["financebench"] = aggregate_financebench_verdicts([
            FinanceBenchVerdict(r["verdict"], r.get("judge_faithfulness", 0.0), "")
            for r in verdicts
        ])

    corrective = [r.get("corrective_rounds") for r in results if r.get("corrective_rounds") is not None]
    if corrective:
        base["corrective_rate"] = round(sum(1 for c in corrective if c > 0) / len(corrective), 4)

    if judge_correctness:
        base["llm_judge"] = {
            "mean_correctness": round(mean(judge_correctness), 2),
            "mean_faithfulness": round(mean(judge_faithfulness), 2) if judge_faithfulness else None,
            "mean_completeness": round(mean(judge_completeness), 2) if judge_completeness else None,
            "hallucination_rate": round(sum(1 for v in judge_hallucinations if v) / len(judge_hallucinations), 4) if judge_hallucinations else None,
            "perfect_faithfulness_rate": round(sum(1 for v in judge_faithfulness if v >= 4) / len(judge_faithfulness), 4) if judge_faithfulness else None,
        }

    return base


def _percent(value: Optional[float]):
    if value is None:
        return None
    return round(value * 100, 2)


def _percent_block(block: Dict) -> Dict:
    out = {}
    for key in ["mean_f1", "context_hit_rate", "supported_rate", "relevant_rate", "hallucination_rate"]:
        if key in block:
            out[key] = _percent(block[key])
    if "retrieval" in block:
        out["retrieval"] = {k: _percent(v) for k, v in block["retrieval"].items()}
    if "financebench" in block:
        fb = block["financebench"]
        out["financebench"] = {
            "accuracy": _percent(fb.get("accuracy")),
            "hallucination_rate": _percent(fb.get("hallucination_rate")),
            "refusal_rate": _percent(fb.get("refusal_rate")),
            "counts": fb.get("counts"),
            "accuracy_ci95": [_percent(v) for v in (fb.get("accuracy_ci95") or [])] or None,
        }
    if "llm_judge" in block:
        out["llm_judge"] = {
            "mean_correctness": block["llm_judge"].get("mean_correctness"),
            "mean_faithfulness": block["llm_judge"].get("mean_faithfulness"),
            "mean_completeness": block["llm_judge"].get("mean_completeness"),
            "hallucination_rate": _percent(block["llm_judge"].get("hallucination_rate")),
            "perfect_faithfulness_rate": _percent(block["llm_judge"].get("perfect_faithfulness_rate")),
        }
    return out


def write_outputs(out_dir: str, per_example: List[Dict], summary: Dict, regressions: List[Dict], errors: List[Dict]):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(per_example, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_regressions.json"), "w", encoding="utf-8") as f:
        json.dump(regressions, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def guard_partial_overwrite(out_dir: str, default_dir: str, partial_reasons: list, force: bool):
    """
    Un run partiel ne doit jamais écraser les sorties versionnées.

    Ces fichiers portent les chiffres cités dans le README et l'étude de cas. Un
    `--max-items 3 --no-judge` lancé pour vérifier que la chaîne tourne les remplaçait
    silencieusement par 3 questions sans verdict — et le prochain `git commit -a` publiait
    ça comme le résultat officiel.
    """
    if force or not partial_reasons:
        return
    if os.path.abspath(out_dir) != os.path.abspath(default_dir):
        return
    raise SystemExit(
        "Refus d'écrire un run partiel (" + ", ".join(partial_reasons) + ") dans les sorties\n"
        f"versionnées ({default_dir}).\n"
        "  --out-dir /tmp/eval-essai   pour un essai jetable\n"
        "  --force-overwrite           si vous voulez vraiment remplacer les chiffres publiés"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/dataset.jsonl", help="Chemin vers le dataset JSONL")
    parser.add_argument("--mode", default="both", choices=["baseline", "agentic", "both"])
    parser.add_argument("--out-dir", default="eval_outputs")
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--k-values", default="10")
    parser.add_argument("--workers", type=int, default=2,
                        help="Questions en parallèle. Passer à 1 en cas de rate limits répétés.")
    parser.add_argument("--no-judge", action="store_true", help="Désactive le juge LLM")
    parser.add_argument("--judge", default="financebench", choices=["financebench", "detailed"],
                        help="financebench: 1 appel, verdict ternaire, comparable au second jeu. "
                             "detailed: 3 appels (correctness/faithfulness/completeness).")
    parser.add_argument("--time-budget", type=int, default=1800,
                        help="Arrêt propre au-delà de N secondes, avec résultats partiels")
    parser.add_argument("--verbose", action="store_true", help="N'étouffe pas les logs du pipeline")
    parser.add_argument("--force-overwrite", action="store_true",
                        help="Autorise un run partiel à écraser les sorties versionnées")
    args = parser.parse_args()

    partial = []
    if args.max_items:
        partial.append(f"--max-items {args.max_items}")
    if args.no_judge:
        partial.append("--no-judge")
    if args.mode != "both":
        partial.append(f"--mode {args.mode}")
    guard_partial_overwrite(args.out_dir, str(ROOT_DIR / "evaluation" / "outputs"), partial,
                            args.force_overwrite)

    # Résoudre le chemin relatif depuis la racine du projet
    dataset_path = args.dataset
    if not os.path.isabs(dataset_path):
        # Si le chemin commence par evaluation/, c'est relatif à la racine
        if dataset_path.startswith("evaluation/"):
            dataset_path = os.path.join(ROOT_DIR, dataset_path)
        # Si le chemin commence par backend/evaluation/, corriger vers evaluation/
        elif dataset_path.startswith("backend/evaluation/"):
            dataset_path = os.path.join(ROOT_DIR, dataset_path.replace("backend/evaluation/", "evaluation/"))
        # Sinon, essayer depuis le répertoire evaluation actuel
        elif not os.path.exists(dataset_path):
            eval_dir = Path(__file__).parent
            potential_path = eval_dir / dataset_path
            if potential_path.exists():
                dataset_path = str(potential_path)

    dataset = load_dataset(dataset_path)
    if args.max_items:
        dataset = dataset[: args.max_items]
    example_labels = _example_labels_for_dataset(dataset_path)
    if args.max_items:
        example_labels = example_labels[: args.max_items]
    if len(example_labels) != len(dataset):
        example_labels = [f"Example {i + 1}" for i in range(len(dataset))]
    k_values = [int(v) for v in args.k_values.split(",") if v.strip()]
    if k_values == [10]:
        k_values = [5, 10, 20]

    modes = ["baseline", "agentic"] if args.mode == "both" else [args.mode]
    dataset = [ex for ex in dataset if ex.get("expected_answer") or ex.get("answer_keywords")]

    _log(f"{len(dataset)} questions | modes: {', '.join(modes)} | workers: {args.workers} "
         f"| juge: {'non' if args.no_judge else args.judge}")

    start = time.time()

    # --- Index -------------------------------------------------------------
    # Construits en série, avant le pool : un retriever par fichier, réutilisé ensuite
    # par tous les threads (la construction touche Chroma, pas les requêtes).
    retrievers = {}
    for example in dataset:
        file_path = resolve_file_path(example)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")
        if file_path not in retrievers:
            retrievers[file_path] = build_retriever_for_file(file_path)
            _log(f"Index prêt : {os.path.basename(file_path)}")

    # --- Agents (instanciés une fois, nœuds sans état -> réutilisables entre threads) ---
    workflow = AgentWorkflow() if "agentic" in modes else None
    researcher = ResearchAgent() if "baseline" in modes else None
    if args.no_judge:
        judge = None
    elif args.judge == "financebench":
        judge = FinanceBenchJudge()
    else:
        judge = LLMJudge() if settings.EVAL_LLM_JUDGE_ENABLED else None

    if not args.verbose:
        sys.stdout = open(os.devnull, "w")

    per_example = []
    truncated = False
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(
                    evaluate_example, ex, retrievers[resolve_file_path(ex)], modes,
                    workflow, researcher, judge, k_values,
                ): (i, ex)
                for i, ex in enumerate(dataset)
            }
            done = 0
            for future in as_completed(futures):
                idx, example = futures[future]
                done += 1
                label = example_labels[idx] if idx < len(example_labels) else f"Example {idx + 1}"
                try:
                    rows = future.result()
                    per_example.extend(rows)
                    status = "/".join(
                        ("ÉCHEC" if r.get("failed") else r.get("verdict", "ok")) for r in rows
                    )
                    _log(f"[{done}/{len(dataset)}] {label} ({example.get('id')}) -> {status}")
                except Exception as e:
                    _log(f"[{done}/{len(dataset)}] {label} ÉCHEC: {root_cause(e)[:160]}")
                    for mode in modes:
                        per_example.append({
                            "id": example.get("id"), "question": example["question"].strip(),
                            "mode": mode, "failed": True, "error": root_cause(e),
                            "rate_limited": is_rate_limit(e),
                        })

                if args.time_budget and time.time() - start > args.time_budget:
                    truncated = True
                    _log(f"⚠️  Budget de {args.time_budget}s dépassé, arrêt avec résultats partiels")
                    for pending in futures:
                        pending.cancel()
                    break
    finally:
        if not args.verbose:
            sys.stdout.close()
            sys.stdout = _REAL_STDOUT

    grouped = defaultdict(list)
    for row in per_example:
        grouped[row["mode"]].append(row)

    summary = {
        "dataset": os.path.basename(dataset_path),
        "n_questions": len(dataset),
        "judge": None if args.no_judge else args.judge,
        "baseline": aggregate(grouped["baseline"], k_values),
        "agentic": aggregate(grouped["agentic"], k_values),
        "elapsed_sec": round(time.time() - start, 2),
        "truncated": truncated,
    }

    b, a = summary["baseline"], summary["agentic"]
    if b.get("count") and a.get("count"):
        summary["delta"] = {
            "mean_f1": round(a["mean_f1"] - b["mean_f1"], 4),
            "context_hit_rate": round(a["context_hit_rate"] - b["context_hit_rate"], 4),
        }
        b_fb, a_fb = b.get("financebench") or {}, a.get("financebench") or {}
        if b_fb.get("counts") and a_fb.get("counts"):
            summary["delta"]["accuracy"] = round(
                a_fb.get("accuracy", 0) - b_fb.get("accuracy", 0), 4)
            summary["delta"]["correct_questions"] = (
                a_fb["counts"]["correct"] - b_fb["counts"]["correct"])

    summary["percent"] = {
        "baseline": _percent_block(summary["baseline"]),
        "agentic": _percent_block(summary["agentic"]),
    }

    regressions = []
    errors = []
    by_id = {}
    for row in per_example:
        if row.get("id") is None:
            continue
        by_id.setdefault(row["id"], {})[row["mode"]] = row

    for ex_id, pair in by_id.items():
        base = pair.get("baseline")
        agent = pair.get("agentic")
        if not base or not agent:
            continue
        if base.get("failed") or agent.get("failed"):
            errors.append({
                "id": ex_id, "question": agent.get("question"), "type": "failed",
                "error": (agent.get("error") or base.get("error")),
                "rate_limited": bool(agent.get("rate_limited") or base.get("rate_limited")),
            })
            continue

        # Régression de verdict : le signal qui compte. Une réponse juste en baseline et
        # fausse une fois passée par les agents est exactement ce que ce jeu doit attraper —
        # c'est ce schéma qui, sur FinanceBench, a révélé que le verdict PARTIAL dégradait
        # la réponse sans déclencher la correction censée le compenser.
        if base.get("verdict") == "CORRECT" and agent.get("verdict") in ("INCORRECT", "REFUSAL"):
            regressions.append({
                "id": ex_id,
                "question": agent["question"],
                "type": "verdict",
                "baseline_verdict": base["verdict"],
                "agentic_verdict": agent["verdict"],
                "relevance": agent.get("relevance"),
                "judge_reason": agent.get("judge_reason"),
            })
        # Régression de F1 : indicatif seulement. Sur des réponses en prose, le
        # recouvrement de tokens ne mesure pas la justesse.
        elif agent["answer_f1"] + 1e-9 < base["answer_f1"]:
            regressions.append({
                "id": ex_id,
                "question": agent["question"],
                "type": "f1",
                "baseline_f1": base["answer_f1"],
                "agentic_f1": agent["answer_f1"],
            })
        if not agent.get("context_hit"):
            errors.append({
                "id": ex_id,
                "question": agent["question"],
                "type": "no_context_hit",
            })

    write_outputs(args.out_dir, per_example, summary, regressions, errors)
    log_to_langsmith(
        name="run_eval",
        summary=summary,
        inputs={"dataset": args.dataset, "mode": args.mode},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
