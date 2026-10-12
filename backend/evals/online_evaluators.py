"""Évaluateurs en ligne LangSmith (onglet "Evaluators" du projet agentic-rag).

Chaque règle note automatiquement les nouvelles traces de production, sans lancer de
script. Ce script crée les règles, ou les met à jour s'il est relancé (même principe que
evaluating-ai-agents/evals/online_evaluators.py).

    uv run python backend/evals/online_evaluators.py            # crée / met à jour, actives
    uv run python backend/evals/online_evaluators.py --disable  # crée / met à jour, coupées

Prérequis : ajouter AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY dans LangSmith (Settings →
Secrets), idéalement d'un utilisateur IAM limité à bedrock:InvokeModel. Les juges tournent sur
les serveurs de LangSmith et y cherchent les clés sous ces noms ; le script ne les envoie jamais.

Juge : Claude Sonnet 4.6 sur Bedrock (avant le 11 oct. 2026 : Mistral Large par l'API Mistral,
dont les verdicts ne sont pas comparables). Choix assumé de tout faire passer par Bedrock : le
juge est de la même famille que l'agent (Claude), qui risque de favoriser ses propres
formulations. L'évaluation FinanceBench garde un juge hors famille Claude (Qwen3 235B).

Quatre règles, une par étape clé de l'agent :

| Règle                      | Run noté                          | Question posée au juge                    |
|----------------------------|-----------------------------------|-------------------------------------------|
| Choix d'outil              | `tool_decision` (search_agent.py) | chercher / répondre : la bonne décision ? |
| Vérificateur de pertinence | `relevance_check`                 | le label CAN_ANSWER/PARTIAL/NO_MATCH ?    |
| Fidélité aux passages      | racine `question` (endpoints.py)  | la réponse ne dit-elle que les passages ? |
| Pertinence de la réponse   | racine `question`                 | la réponse traite-t-elle la question ?    |
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config.settings import settings  # noqa: E402  (charge aussi le .env)
from backend.evals.feedback.votes import TRACE_PROJECT  # noqa: E402

# Préfixe des règles créées par ce script : le nom du projet, pour savoir à quel projet
# appartient chaque évaluateur dans LangSmith (et retrouver les règles pour les mettre à jour)
RULE_PREFIX = f"{TRACE_PROJECT} · "
JUDGE_MODEL = "eu.anthropic.claude-sonnet-4-6"  # profil d'inférence « eu. », appelable de Paris
JUDGE_REGION = "eu-west-3"
SAMPLING_RATE = 1.0  # toutes les traces : le trafic est faible, ~0,01-0,04 $ par question

TOOL_SELECTION_PROMPT = """Tu évalues une décision d'un agent qui répond à des questions sur des documents.
À chaque tour, l'agent choisit : appeler un de ses outils de recherche (search, grep, read_page,
open_doc, navigate) pour trouver ce qui manque, ou répondre avec les passages qu'il a déjà.
Le message système décrit les outils et le budget d'appels.

[DÉBUT DES DONNÉES]
Conversation jusqu'à la décision : {{messages}}

Décision de l'agent : {{decision}}
[FIN DES DONNÉES]

La décision est correcte si : l'agent répond quand les passages déjà vus suffisent, ou cherche
quand une information nécessaire manque, avec un outil et des arguments adaptés à ce qui manque.
Elle est incorrecte s'il cherche alors que la réponse est déjà dans les passages, s'il répond
sans l'information nécessaire, ou s'il relance une recherche quasi identique à une précédente.
Évalue uniquement cette décision, pas la qualité finale de la réponse.
Écris d'abord ton raisonnement, puis ton verdict.
"""

RELEVANCE_CHECK_PROMPT = """Tu évalues un vérificateur de pertinence. Il lit une question et les premiers
passages retrouvés, puis donne un label :
- CAN_ANSWER : les passages contiennent assez d'informations explicites pour répondre complètement ;
- PARTIAL : les passages traitent du sujet ou de la période, sans tout ce qu'il faut pour répondre ;
- NO_MATCH : les passages ne parlent pas du tout du sujet de la question.

[DÉBUT DES DONNÉES]
Question : {{question}}

Passages : {{passages}}

Label donné : {{verdict}}
[FIN DES DONNÉES]

Le label est-il correct ? Un choix défendable entre deux labels voisins passe ; un CAN_ANSWER
sur des passages qui ne contiennent pas la réponse, ou un NO_MATCH sur des passages qui en
parlent, échoue.
Écris d'abord ton raisonnement, puis ton verdict.
"""

FAITHFULNESS_PROMPT = """Tu vérifies qu'une réponse générée à partir de documents ne dit rien de plus que
ce que contiennent les passages que le modèle a vus (numérotés [n]).

[DÉBUT DES DONNÉES]
Question : {{question}}

Passages vus par le modèle : {{context}}

Réponse : {{answer}}
[FIN DES DONNÉES]

La réponse est fidèle si chaque chiffre, date, nom et affirmation factuelle se retrouve dans les
passages (un calcul exact à partir des passages compte comme fidèle). Elle échoue si elle
affirme un fait absent des passages ou qui les contredit. Une réponse qui dit ne pas trouver
l'information est fidèle.
Écris d'abord ton raisonnement, puis ton verdict.
"""

ANSWER_RELEVANCE_PROMPT = """Tu vérifies qu'une réponse traite bien la question posée.

[DÉBUT DES DONNÉES]
Question : {{question}}

Réponse : {{answer}}
[FIN DES DONNÉES]

La réponse est pertinente si elle répond à la question posée (la bonne métrique, la bonne
période, la bonne entité), sans se perdre dans des développements hors sujet. Elle échoue si
elle répond à une autre question, reste évasive, ou noie la réponse dans du hors sujet. Ne
juge pas l'exactitude des chiffres, seulement si la réponse vise la question.
Écris d'abord ton raisonnement, puis ton verdict.
"""

_ROOT_QUESTION = 'and(eq(is_root, true), eq(name, "question"))'


def serialized_judge() -> dict:
    """
    Juge Claude (Bedrock) sérialisé sans les clés : la sérialisation ne garde que les noms des
    secrets (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY), que LangSmith lit dans ses secrets.
    """
    from langchain_aws import ChatBedrockConverse
    from langchain_core.load import dumpd
    return dumpd(ChatBedrockConverse(model=JUDGE_MODEL, region_name=JUDGE_REGION, temperature=0,
                                     aws_access_key_id="secret-lu-par-langsmith",
                                     aws_secret_access_key="secret-lu-par-langsmith"))


def llm_judge(key: str, description: str, prompt: str, variable_mapping: dict, judge: dict) -> dict:
    """Juge LLM en ligne : le score (booléen) devient le feedback `key`, avec son raisonnement."""
    return {"structured": {
        "prompt": [["human", prompt]],
        # Mustache ({{variable}}) : c'est ce format que LangSmith résout via variable_mapping
        # (comme langsmith-cli). En f-string, les variables arrivaient au juge à « None ».
        "template_format": "mustache",
        "variable_mapping": variable_mapping,
        "model": judge,
        "schema": {
            "title": key,
            "description": description,
            "type": "object",
            "properties": {
                # Le raisonnement d'abord : le modèle écrit sa justification avant le verdict.
                "comment": {"type": "string", "description": "Raisonnement détaillé, avant le verdict"},
                key: {"type": "boolean", "description": description},
            },
            "required": ["comment", key],
        },
    }}


def rules(judge: dict) -> list:
    return [
        {
            "display_name": "Choix d'outil",
            "filter": 'eq(name, "tool_decision")',
            "evaluators": [llm_judge(
                "tool_selection", "Vrai si l'agent a pris la bonne décision (chercher ou répondre)",
                TOOL_SELECTION_PROMPT, {"messages": "inputs.messages", "decision": "outputs"}, judge,
            )],
        },
        {
            "display_name": "Vérificateur de pertinence",
            "filter": 'eq(name, "relevance_check")',
            "evaluators": [llm_judge(
                "relevance_check_correct", "Vrai si le label du vérificateur est correct",
                RELEVANCE_CHECK_PROMPT,
                {"question": "inputs.question", "passages": "inputs.passages", "verdict": "outputs.output"},
                judge,
            )],
        },
        {
            "display_name": "Fidélité aux passages",
            "filter": _ROOT_QUESTION,
            "evaluators": [llm_judge(
                "faithfulness", "Vrai si la réponse ne dit que ce que contiennent les passages",
                FAITHFULNESS_PROMPT,
                {"question": "inputs.question", "context": "outputs.context_used",
                 "answer": "outputs.draft_answer"},
                judge,
            )],
        },
        {
            "display_name": "Pertinence de la réponse",
            "filter": _ROOT_QUESTION,
            "evaluators": [llm_judge(
                "answer_relevance", "Vrai si la réponse traite la question posée",
                ANSWER_RELEVANCE_PROMPT,
                {"question": "inputs.question", "answer": "outputs.draft_answer"}, judge,
            )],
        },
    ]


def _api(client, method: str, path: str, **kwargs):
    response = client.session.request(
        method, f"{client.api_url}/api/v1{path}",
        headers={"x-api-key": client.api_key}, timeout=30, **kwargs,
    )
    if not response.ok:
        raise RuntimeError(f"{method} {path} → {response.status_code} : {response.text}")
    return response.json() if response.content else None


def setup_online_evaluators(enabled: bool = True) -> int:
    if not settings.LANGSMITH_API_KEY:
        print("✗ LANGSMITH_API_KEY absente : rien à configurer.", file=sys.stderr)
        return 1
    from langsmith import Client
    client = Client(api_key=settings.LANGSMITH_API_KEY)
    project_id = str(client.read_project(project_name=TRACE_PROJECT).id)
    existing = {
        rule["display_name"]: rule
        for rule in _api(client, "GET", "/runs/rules", params={"session_id": project_id})
    }

    for rule in rules(serialized_judge()):
        payload = {
            **rule,
            "display_name": RULE_PREFIX + rule["display_name"],
            "session_id": project_id,
            "sampling_rate": SAMPLING_RATE,
            "is_enabled": enabled,
            # Pas de trace des juges dans un projet « evaluators » : le verdict et son
            # raisonnement restent sur la trace notée (feedback), c'est là qu'on les lit.
            "is_tracing_disabled": True,
        }
        # Mise à jour plutôt que suppression + recréation : recréer une règle crée aussi un
        # nouvel évaluateur et un nouveau dataset de corrections dans LangSmith.
        state = "active" if enabled else "coupée"
        if payload["display_name"] in existing:
            _api(client, "PATCH", f"/runs/rules/{existing[payload['display_name']]['id']}", json=payload)
            print(f"· règle mise à jour : {payload['display_name']} ({state})")
        else:
            _api(client, "POST", "/runs/rules", json=payload)
            print(f"✓ règle créée : {payload['display_name']} ({state})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Évaluateurs en ligne LangSmith (agentic-rag)")
    parser.add_argument("--disable", action="store_true", help="crée ou met à jour les règles, coupées")
    args = parser.parse_args()
    return setup_online_evaluators(enabled=not args.disable)


if __name__ == "__main__":
    sys.exit(main())
