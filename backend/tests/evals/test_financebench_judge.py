"""Ces tests échouaient sur main au 1er sept. 2026 : les constantes REFUSAL_MARKERS / ERROR_MARKERS /
FINANCEBENCH_JUDGE_PROMPT avaient été supprimées par le commit 'nettoyage du code mort' (441321e)
alors que FinanceBenchJudge les utilise encore -> NameError au premier jugement."""
from backend.evals.experiment_utils import FinanceBenchJudge


def test_canned_refusals_are_detected_without_llm():
    assert FinanceBenchJudge.detect_canned_response(
        "Cette question n'est pas liée (ou il n'y a pas de données) pour votre requête."
    ) == "REFUSAL"
    assert FinanceBenchJudge.detect_canned_response("Cette information n'est pas disponible dans le document.") == "REFUSAL"


def test_canned_errors_are_detected_and_real_answers_pass():
    assert FinanceBenchJudge.detect_canned_response("Une erreur est survenue lors de la génération de la réponse.") == "ERROR"
    assert FinanceBenchJudge.detect_canned_response("") == "ERROR"
    assert FinanceBenchJudge.detect_canned_response("Net revenue was $52.9 billion [1].") is None


def test_canned_refusal_must_be_the_whole_answer():
    """Régression du 2 sept. 2026 : la détection par sous-chaîne classait REFUSAL des réponses
    complètes qui signalaient au passage qu'un point secondaire manquait. Les 6 verdicts REFUSAL
    du run portaient tous sur des réponses de 300 à 1900 caractères, jamais jugées par le LLM."""
    complete = (
        "The operating margin change for AMD in FY22 was driven by a decrease in operating income "
        "to $1.3 billion in 2022 from $3.6 billion in 2021 [1], and by amortization of intangible "
        "assets associated with the Xilinx acquisition [2].\n\n"
        "### Is operating margin a useful metric for AMD?\n"
        "The context does not explicitly state it. **Cette information n'est pas disponible dans le document.** [1][2]"
    )
    assert FinanceBenchJudge.detect_canned_response(complete) is None


def test_standalone_refusal_still_short_circuits_even_in_bold():
    assert FinanceBenchJudge.detect_canned_response(
        "**Cette information n'est pas disponible dans le document.**"
    ) == "REFUSAL"
    assert FinanceBenchJudge.detect_canned_response(
        "Cette question n'est pas liée (ou il n'y a pas de données) pour votre requête. "
        "Veuillez poser une autre question pertinente aux document(s) téléchargé(s)."
    ) == "REFUSAL"


def test_error_markers_only_match_at_the_start():
    assert FinanceBenchJudge.detect_canned_response(
        "Une erreur est survenue lors de la génération de la réponse. Réessayez."
    ) == "ERROR"
    # Le modèle qui *cite* une erreur du document ne doit pas être compté comme panne technique.
    assert FinanceBenchJudge.detect_canned_response(
        "Boeing indique dans son 10-K qu'une erreur est survenue lors du traitement de votre question "
        "n'est pas une phrase du filing ; la réponse attendue est $66,608 millions [3]."
    ) is None


def test_judge_reads_cited_passages_first():
    """3M 2018 : le PP&E net cité [3] venait d'une page lue par un outil, au-delà des 6 000
    premiers caractères ; le juge le prenait pour une invention."""
    from types import SimpleNamespace
    from backend.evals.experiment import judge_context
    docs = [SimpleNamespace(page_content=t) for t in ("intro", "bruit", "Net PP&E 8,738")]
    assert judge_context("PP&E net : 8 738 M$ [3], voir aussi [1] et [9].", docs).split("\n\n") == [
        "Net PP&E 8,738", "intro", "bruit"]
    assert judge_context("sans citation", docs).split("\n\n") == ["intro", "bruit", "Net PP&E 8,738"]


def test_judge_never_sees_the_annotation_of_the_question_it_grades():
    examples = [{"question": "Q1 ?", "reference": "a", "answer": "b", "verdict": "CORRECT", "comment": "ok"},
                {"question": "Q2 ?", "reference": "c", "answer": "d", "verdict": "INCORRECT", "comment": ""}]
    block = FinanceBenchJudge(llm=object(), examples=examples).examples_block("  q1  ?")
    assert "Q2 ?" in block and "Q1 ?" not in block


def test_numeric_match_on_real_answers():
    from backend.evals.experiment_utils import numeric_match
    # même valeur à une autre échelle, virgule de milliers, parenthèses comptables
    assert numeric_match("$8.70", "Le net PP&E de 3M est de **$8,738 millions** [11].")
    assert numeric_match("$1577.00", "3M's FY2018 capex was **$(1,577) million** [11].")
    assert numeric_match("16.5%", "**EBITDA % margin FY2022 : 16.5%**")
    # arrondi de la référence : −0,0153 s'arrondit à −0,02, pas −0,0142
    assert numeric_match("-0.02", "**Données :**\nROA = −546 / 35 663 = **−0.0153**, soit −0.02")
    assert not numeric_match("-0.02", "**AES's FY2022 ROA = –1.42%**")
    assert not numeric_match("24.26", "**FY2019 Fixed Asset Turnover Ratio = 24.00**")
    assert not numeric_match("70", "Pfizer expects total costs of **$700 million** [1].")
    # référence non numérique : pas de contrôle
    assert not numeric_match("Yes, it's spinning off Upjohn.", "Yes")
    assert not numeric_match("0", "Les coûts de restructuration s'élèvent à $0.3 million [2].")
