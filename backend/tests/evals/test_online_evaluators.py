"""Évaluateurs en ligne : règles bien formées, et runs nommés que ces règles notent."""
import json
import re
from unittest.mock import MagicMock

import langsmith
from langchain_core.messages import AIMessage, HumanMessage

from backend.agents import search_agent
from backend.agents.relevance_checker import RelevanceChecker
from backend.evals.online_evaluators import RULE_PREFIX, rules, serialized_judge
from conftest import FakeLLM, make_doc


def _rules():
    return rules(serialized_judge())


def test_four_rules_one_per_key_step():
    assert [r["display_name"] for r in _rules()] == [
        "Choix d'outil", "Vérificateur de pertinence", "Fidélité aux passages", "Pertinence de la réponse",
    ]
    assert not any(r["display_name"].startswith(RULE_PREFIX) for r in _rules())  # ajouté à l'envoi


def test_every_prompt_variable_is_mapped_exactly_once():
    for rule in _rules():
        judge = rule["evaluators"][0]["structured"]
        variables = set(re.findall(r"\{\{(\w+)\}\}", judge["prompt"][0][1]))
        assert variables == set(judge["variable_mapping"]), rule["display_name"]


def test_prompts_use_mustache_so_langsmith_fills_the_variables():
    for rule in _rules():
        judge = rule["evaluators"][0]["structured"]
        assert judge["template_format"] == "mustache"
        assert not re.search(r"(?<!\{)\{\w+\}(?!\})", judge["prompt"][0][1]), rule["display_name"]


def test_verdict_is_binary_with_reasoning_first():
    for rule in _rules():
        schema = rule["evaluators"][0]["structured"]["schema"]
        key = schema["title"]
        assert schema["properties"][key]["type"] == "boolean"
        assert schema["required"] == ["comment", key]


def test_judge_is_claude_on_bedrock_and_never_carries_the_keys():
    judge = serialized_judge()
    assert judge["id"][-1] == "ChatBedrockConverse"
    assert judge["kwargs"]["model_id"] == "eu.anthropic.claude-sonnet-4-6"
    # Les clés sont des références aux secrets LangSmith, jamais leur valeur.
    for name in ("aws_access_key_id", "aws_secret_access_key"):
        assert judge["kwargs"][name] == {"lc": 1, "type": "secret", "id": [name.upper()]}
    assert "secret-lu-par-langsmith" not in json.dumps(judge)


def test_answer_rules_target_the_root_question_run():
    filters = {r["display_name"]: r["filter"] for r in _rules()}
    assert filters["Fidélité aux passages"] == 'and(eq(is_root, true), eq(name, "question"))'
    assert filters["Choix d'outil"] == 'eq(name, "tool_decision")'
    assert filters["Vérificateur de pertinence"] == 'eq(name, "relevance_check")'


# ── Runs nommés : le contrat entre le code de l'agent et les règles ───────────

def _traced_runs(fn):
    client = MagicMock()
    with langsmith.tracing_context(enabled=True, client=client, project_name="test"):
        fn()
    return [c.kwargs for c in client.method_calls if c[0] == "create_run"]


def test_tool_decision_is_a_named_run_with_the_conversation_as_input():
    class Bound:
        def invoke(self, messages):
            return AIMessage(content="réponse")

    runs = _traced_runs(lambda: search_agent._tool_decision(Bound(), [HumanMessage(content="q")]))
    assert [r["name"] for r in runs] == ["tool_decision"]
    assert list(runs[0]["inputs"]) == ["messages"]  # le modèle lié n'est pas tracé


def test_relevance_check_traces_question_and_only_the_judged_passages():
    checker = RelevanceChecker()
    checker.model = FakeLLM(["PARTIAL"])
    docs = [make_doc(f"passage {i}") for i in range(5)]

    runs = _traced_runs(lambda: checker.check("quel CA ?", docs, k=2))
    assert [r["name"] for r in runs] == ["relevance_check"]
    assert runs[0]["inputs"] == {"question": "quel CA ?", "passages": "passage 0\n\npassage 1"}


def test_tool_loop_behaviour_is_unchanged_by_tracing():
    class ToolLLM:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="fin")

    messages = [HumanMessage(content="q")]
    out = search_agent.run_tool_loop(ToolLLM(), [], messages, max_tool_calls=3)
    assert out == {"tool_calls": 0, "final": messages[-1]}
    assert len(messages) == 2  # la copie passée au run tracé n'a pas changé la conversation
