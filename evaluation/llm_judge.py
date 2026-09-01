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





@dataclass
class FinanceBenchVerdict:
    """Résultat du juge FinanceBench pour une réponse."""
    verdict: str  # CORRECT | INCORRECT | REFUSAL | ERROR
    faithfulness: float  # 1-5
    reason: str

    @property
    def is_correct(self) -> bool:
        return self.verdict == "CORRECT"

    @property
    def is_refusal(self) -> bool:
        return self.verdict == "REFUSAL"

    @property
    def is_hallucination(self) -> bool:
        """Répond avec assurance mais se trompe — la métrique centrale de FinanceBench."""
        return self.verdict == "INCORRECT"


class FinanceBenchJudge:
    """
    Juge LLM au protocole FinanceBench : un appel, un verdict ternaire + faithfulness.
    """

    VALID_VERDICTS = {"CORRECT", "INCORRECT", "REFUSAL"}

    def __init__(self, llm=None, model: Optional[str] = None):
        self.llm = llm
        self.model = model or settings.MODEL_ID

    def _get_llm(self):
        if self.llm is None:
            self.llm = ChatMistralAI(
                model=self.model,
                api_key=settings.MISTRALAI_API_KEY,
                temperature=0,
                max_tokens=250,
                timeout=settings.LLM_TIMEOUT,
                max_retries=settings.LLM_MAX_RETRIES,
            )
        return self.llm

    @staticmethod
    def detect_canned_response(answer: str) -> Optional[str]:
        """
        Détecte sans appel LLM les messages figés du pipeline.
        Retourne "REFUSAL", "ERROR", ou None.
        """
        low = (answer or "").strip().lower()
        if not low:
            return "ERROR"
        if any(m in low for m in ERROR_MARKERS):
            return "ERROR"
        if any(m in low for m in REFUSAL_MARKERS):
            return "REFUSAL"
        return None

    def _parse(self, response: str) -> FinanceBenchVerdict:
        verdict = "INCORRECT"
        m = re.search(r"VERDICT:\s*\[?\s*(CORRECT|INCORRECT|REFUSAL)", response, re.IGNORECASE)
        if m:
            verdict = m.group(1).upper()

        faithfulness = 3.0
        m = re.search(r"FAITHFULNESS:\s*\[?\s*(\d(?:\.\d)?)", response, re.IGNORECASE)
        if m:
            try:
                faithfulness = max(1.0, min(5.0, float(m.group(1))))
            except ValueError:
                pass

        reason = "Impossible de parser la réponse du juge"
        m = re.search(r"RAISON:\s*(.+?)(?:\n\s*\n|$)", response, re.IGNORECASE | re.DOTALL)
        if m:
            reason = " ".join(m.group(1).split())

        return FinanceBenchVerdict(verdict=verdict, faithfulness=faithfulness, reason=reason)

    def evaluate(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str,
        context: str,
        justification: str = "",
        max_context_len: int = 6000,
    ) -> FinanceBenchVerdict:
        """Juge une réponse. Les messages figés du pipeline court-circuitent l'appel LLM."""
        canned = self.detect_canned_response(generated_answer)
        if canned == "ERROR":
            return FinanceBenchVerdict("ERROR", 0.0, "Erreur technique du pipeline (timeout ou LLM indisponible)")
        if canned == "REFUSAL":
            return FinanceBenchVerdict("REFUSAL", 5.0, "Refus explicite du pipeline (message figé)")

        if len(context) > max_context_len:
            context = context[:max_context_len] + "..."

        prompt = FINANCEBENCH_JUDGE_PROMPT.format(
            question=question,
            expected_answer=expected_answer or "(non fournie)",
            justification=justification or "(non fournie)",
            generated_answer=generated_answer,
            context=context or "(aucun extrait)",
        )
        try:
            response = self._get_llm().invoke(prompt)
            return self._parse(response.content)
        except Exception as e:
            # Un rate limit doit remonter à l'appelant pour être rejoué (backoff) ;
            # l'avaler en verdict ERROR fausserait le dénominateur de l'accuracy.
            from evaluation.utils import is_rate_limit
            if is_rate_limit(e):
                raise
            logger.warning(f"FinanceBenchJudge error: {e}")
            return FinanceBenchVerdict("ERROR", 0.0, f"Erreur du juge: {type(e).__name__}: {e}")


def aggregate_financebench_verdicts(verdicts: List[FinanceBenchVerdict]) -> Dict:
    """
    Agrège au protocole FinanceBench.
    Les erreurs techniques sont exclues du dénominateur et comptées à part.
    """
    if not verdicts:
        return {}

    scored = [v for v in verdicts if v.verdict != "ERROR"]
    errors = len(verdicts) - len(scored)
    if not scored:
        return {"count": 0, "errors": errors}

    n = len(scored)
    faith = [v.faithfulness for v in scored if v.faithfulness > 0]
    return {
        "count": n,
        "errors": errors,
        "accuracy": round(sum(1 for v in scored if v.is_correct) / n, 4),
        "refusal_rate": round(sum(1 for v in scored if v.is_refusal) / n, 4),
        "hallucination_rate": round(sum(1 for v in scored if v.is_hallucination) / n, 4),
        "mean_faithfulness": round(sum(faith) / len(faith), 2) if faith else None,
    }
