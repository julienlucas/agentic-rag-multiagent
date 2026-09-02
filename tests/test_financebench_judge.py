"""Ces tests échouaient sur main au 1er sept. 2026 : les constantes REFUSAL_MARKERS / ERROR_MARKERS /
FINANCEBENCH_JUDGE_PROMPT avaient été supprimées par le commit 'nettoyage du code mort' (441321e)
alors que FinanceBenchJudge les utilise encore -> NameError au premier jugement."""
from evaluation.llm_judge import FinanceBenchJudge


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
