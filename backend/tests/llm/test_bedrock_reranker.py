"""Rerank Cohere 3.5 sur Bedrock : appel à l'API Rerank de la bonne région, réponse au format Cohere."""
from backend.config.settings import settings
from backend.llm import bedrock


class FakeAgentRuntime:
    def __init__(self):
        self.kwargs = None

    def rerank(self, **kwargs):
        self.kwargs = kwargs
        return {"results": [{"index": 1, "relevanceScore": 0.9}, {"index": 0, "relevanceScore": 0.2}]}


def test_bedrock_reranker_calls_the_rerank_region_and_returns_cohere_shaped_results(monkeypatch):
    fake = FakeAgentRuntime()
    seen = {}
    monkeypatch.setattr(bedrock, "_client", lambda service, region, timeout: seen.update(s=service, r=region) or fake)

    response = bedrock.BedrockReranker().rerank("cohere.rerank-v3-5:0", "revenue ?", ["a", "b"], top_n=2)

    assert seen == {"s": "bedrock-agent-runtime", "r": settings.RERANK_REGION}
    config = fake.kwargs["rerankingConfiguration"]["bedrockRerankingConfiguration"]
    assert config["numberOfResults"] == 2
    assert config["modelConfiguration"]["modelArn"] == (
        f"arn:aws:bedrock:{settings.RERANK_REGION}::foundation-model/cohere.rerank-v3-5:0")
    assert [(r.index, r.relevance_score) for r in response.results] == [(1, 0.9), (0, 0.2)]
    assert response.meta is None
