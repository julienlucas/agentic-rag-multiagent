import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from langchain_mistralai import ChatMistralAI

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config.settings import settings
from backend.utils.logging import logger


@dataclass
class JudgeResult:
    """Résultat de l'évaluation LLM-as-a-Judge."""
    correctness: float  # 1-5: La réponse est-elle correcte?
    faithfulness: float  # 1-5: Tout est-il supporté par le contexte?
    completeness: float  # 1-5: Tous les points sont-ils couverts?
    correctness_reason: str
    faithfulness_reason: str
    completeness_reason: str
    is_hallucination: bool  # True si faithfulness < 3


CORRECTNESS_PROMPT = """Tu es un évaluateur expert. Évalue si la réponse générée est correcte par rapport à la réponse attendue.

Question: {question}

Réponse attendue (ground truth): {expected_answer}

Réponse générée: {generated_answer}

Évalue la CORRECTNESS (exactitude) sur une échelle de 1 à 5:
- 5: Parfaitement correct, tous les faits correspondent
- 4: Correct avec des détails mineurs différents
- 3: Partiellement correct, certains faits sont justes
- 2: Majoritairement incorrect, peu de faits justes
- 1: Complètement incorrect ou hors sujet

Réponds EXACTEMENT dans ce format:
SCORE: [1-5]
RAISON: [Explication courte en 1-2 phrases]"""


FAITHFULNESS_PROMPT = """Tu es un évaluateur expert. Évalue si TOUT ce qui est dit dans la réponse est supporté par le contexte fourni.

Question: {question}

Contexte fourni (documents récupérés):
{context}

Réponse générée: {generated_answer}

Évalue la FAITHFULNESS (fidélité au contexte) sur une échelle de 1 à 5:
- 5: 100% fidèle, tout est explicitement dans le contexte
- 4: Très fidèle, inférences mineures raisonnables
- 3: Partiellement fidèle, quelques affirmations non supportées
- 2: Peu fidèle, plusieurs affirmations inventées
- 1: Non fidèle, hallucinations majeures ou contredisant le contexte

IMPORTANT: Une réponse qui dit "je ne sais pas" ou "l'information n'est pas dans le document" quand c'est vrai = score 5.

Réponds EXACTEMENT dans ce format:
SCORE: [1-5]
RAISON: [Explication courte en 1-2 phrases]"""


COMPLETENESS_PROMPT = """Tu es un évaluateur expert. Évalue si la réponse couvre tous les points importants de la question et de la réponse attendue.

Question: {question}

Réponse attendue (ground truth): {expected_answer}

Réponse générée: {generated_answer}

Évalue la COMPLETENESS (complétude) sur une échelle de 1 à 5:
- 5: Tous les points importants couverts, rien de manquant
- 4: La plupart des points couverts, manque mineur
- 3: Points principaux couverts, plusieurs détails manquants
- 2: Réponse incomplète, points majeurs manquants
- 1: Très incomplète ou ne répond pas à la question

Réponds EXACTEMENT dans ce format:
SCORE: [1-5]
RAISON: [Explication courte en 1-2 phrases]"""


class LLMJudge:
    """
    Évaluateur LLM-as-a-Judge pour mesurer la qualité des réponses RAG.
    """

    def __init__(self, llm=None):
        """
        Args:
            llm: LLM pour l'évaluation (optionnel, utilise Mistral par défaut)
        """
        self.llm = llm
        self.enabled = settings.EVAL_LLM_JUDGE_ENABLED

    def _get_llm(self):
        """Initialise le LLM si nécessaire."""
        if self.llm is None:
            self.llm = ChatMistralAI(
                model=settings.MODEL_ID,
                api_key=settings.MISTRALAI_API_KEY,
                temperature=0,  # Déterministe pour l'évaluation
                max_tokens=200,
            )
        return self.llm

    def _parse_score(self, response: str) -> tuple[float, str]:
        """
        Parse le score et la raison depuis la réponse du LLM.

        Returns:
            (score, reason)
        """
        score = 3.0  # Default
        reason = "Impossible de parser la réponse"

        # Parser le score
        score_match = re.search(r"SCORE:\s*(\d(?:\.\d)?)", response, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
                score = max(1.0, min(5.0, score))  # Clamp entre 1 et 5
            except ValueError:
                pass

        # Parser la raison
        reason_match = re.search(r"RAISON:\s*(.+?)(?:\n|$)", response, re.IGNORECASE | re.DOTALL)
        if reason_match:
            reason = reason_match.group(1).strip()

        return score, reason

    def evaluate_correctness(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str
    ) -> tuple[float, str]:
        """Évalue l'exactitude de la réponse."""
        if not self.enabled:
            return 0.0, "LLM Judge désactivé"

        try:
            llm = self._get_llm()
            prompt = CORRECTNESS_PROMPT.format(
                question=question,
                expected_answer=expected_answer,
                generated_answer=generated_answer
            )
            response = llm.invoke(prompt)
            return self._parse_score(response.content)
        except Exception as e:
            logger.warning(f"LLMJudge correctness error: {e}")
            return 0.0, f"Erreur: {e}"

    def evaluate_faithfulness(
        self,
        question: str,
        context: str,
        generated_answer: str
    ) -> tuple[float, str]:
        """Évalue la fidélité au contexte (anti-hallucination)."""
        if not self.enabled:
            return 0.0, "LLM Judge désactivé"

        try:
            llm = self._get_llm()
            # Tronquer le contexte si trop long
            max_context_len = 4000
            if len(context) > max_context_len:
                context = context[:max_context_len] + "..."

            prompt = FAITHFULNESS_PROMPT.format(
                question=question,
                context=context,
                generated_answer=generated_answer
            )
            response = llm.invoke(prompt)
            return self._parse_score(response.content)
        except Exception as e:
            logger.warning(f"LLMJudge faithfulness error: {e}")
            return 0.0, f"Erreur: {e}"

    def evaluate_completeness(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str
    ) -> tuple[float, str]:
        """Évalue la complétude de la réponse."""
        if not self.enabled:
            return 0.0, "LLM Judge désactivé"

        try:
            llm = self._get_llm()
            prompt = COMPLETENESS_PROMPT.format(
                question=question,
                expected_answer=expected_answer,
                generated_answer=generated_answer
            )
            response = llm.invoke(prompt)
            return self._parse_score(response.content)
        except Exception as e:
            logger.warning(f"LLMJudge completeness error: {e}")
            return 0.0, f"Erreur: {e}"

    def evaluate(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str,
        context: str
    ) -> JudgeResult:
        """
        Évaluation complète sur les 3 métriques.

        Args:
            question: La question posée
            expected_answer: La réponse attendue (ground truth)
            generated_answer: La réponse générée par le RAG
            context: Le contexte (documents récupérés concaténés)

        Returns:
            JudgeResult avec les 3 scores et raisons
        """
        correctness, correctness_reason = self.evaluate_correctness(
            question, expected_answer, generated_answer
        )
        faithfulness, faithfulness_reason = self.evaluate_faithfulness(
            question, context, generated_answer
        )
        completeness, completeness_reason = self.evaluate_completeness(
            question, expected_answer, generated_answer
        )

        # Hallucination = faithfulness < 3
        is_hallucination = faithfulness < 3.0

        return JudgeResult(
            correctness=correctness,
            faithfulness=faithfulness,
            completeness=completeness,
            correctness_reason=correctness_reason,
            faithfulness_reason=faithfulness_reason,
            completeness_reason=completeness_reason,
            is_hallucination=is_hallucination
        )

    def evaluate_batch(
        self,
        examples: List[Dict]
    ) -> List[JudgeResult]:
        """
        Évalue un batch d'exemples.

        Args:
            examples: Liste de dicts avec keys:
                - question
                - expected_answer
                - generated_answer
                - context

        Returns:
            Liste de JudgeResult
        """
        results = []
        for ex in examples:
            result = self.evaluate(
                question=ex.get("question", ""),
                expected_answer=ex.get("expected_answer", ""),
                generated_answer=ex.get("generated_answer", ""),
                context=ex.get("context", "")
            )
            results.append(result)
        return results


def aggregate_judge_results(results: List[JudgeResult]) -> Dict:
    """
    Agrège les résultats du LLM Judge.

    Returns:
        Dict avec moyennes et taux
    """
    if not results:
        return {}

    valid_results = [r for r in results if r.correctness > 0]
    if not valid_results:
        return {}

    return {
        "mean_correctness": round(sum(r.correctness for r in valid_results) / len(valid_results), 2),
        "mean_faithfulness": round(sum(r.faithfulness for r in valid_results) / len(valid_results), 2),
        "mean_completeness": round(sum(r.completeness for r in valid_results) / len(valid_results), 2),
        "hallucination_rate": round(sum(1 for r in valid_results if r.is_hallucination) / len(valid_results), 4),
        "perfect_faithfulness_rate": round(sum(1 for r in valid_results if r.faithfulness >= 4) / len(valid_results), 4),
        "count": len(valid_results)
    }
