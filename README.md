![RAG Agentique multi-agent Header](./static/header.png)

# RAG Agentique multi-agent haute précision, anti-hallucinations (évalué sur FinanceBench)

Ce système RAG agentique combine des agents spécialisés et un récupérateur avancé (BM25 + embeddings + reranking) pour une haute précision dans la recherche de documents — mesurée sur [FinanceBench](https://github.com/patronus-ai/financebench), le benchmark utilisé par Mistral pour évaluer Agentic Search.


![Image 1](./static/chatgpt-test.png)
GPT 4o halucine, les stats de tableaux récupérées ne sont pas les bonnes.

![Image 2](./static/deepseek-test.png)
DeepSeek R1 s'arrête il n'arrive pas à lire le document en entier.

## Architecture IA

![Projet Overview](./static/project-overview.jpg)

### 1. **Agent Vérificateur de Pertinence**
Évalue si les passages récupérés répondent réellement à la question (CAN_ANSWER / PARTIAL / NO_MATCH).

### 2. **Agent de Recherche Corrective**
Si les passages sont insuffisants (ou que le score du reranker est faible), il réécrit la question dans le vocabulaire du document (ex. « legal battles » → *litigation*) et relance la recherche avant de répondre ou de refuser.

### 3. **Agent de Recherche**
Génère la réponse finale, contrainte aux seuls passages récupérés — refuse explicitement quand l'information n'y est pas.

### Le système inclut un retriever hybride pour maximiser la pertinence
- **Algo BM25 + Embeddings** : Recherche texte classique à forte précision lexicale + Recherche sémantique capturant le sens contextuel.
- **Routage par document** : avant de chercher, le système cible le(s) document(s) que la question désigne (nom d'entreprise ou de fichier) — indispensable quand plusieurs documents longs sont indexés ensemble.
- **Reranking Cohere + parent-child + multi-query** : petits chunks pour matcher, gros chunks pour répondre.

## Stack de modèles
- ⚡ Mistral OCR (plutôt que docling trop lent)
- 🧠 Mistral Embed (embeddings)
- 🧠 Cohere Rerank v4 Pro multi-langue
- 💎 Mistral Large (génération) + Mistral Small (sous-agents : pertinence, routage, réécriture)

## Installation

1. **Cloner le projet** :
```bash
git clone https://github.com/julienlucas/agentic-rag-multi-agent
```

2. **Installer les dépendances** :
```bash
python3.12 -m venv venv
source venv/bin/activate
poetry install
```

3. **Configuration** :
Allez sur https://console.mistral.ai pour créer votre clé.

Puis créer un fichier `.env` avec vos clés ([console.mistral.ai](https://console.mistral.ai) et [dashboard.cohere.com](https://dashboard.cohere.com)) :
```bash
MISTRALAI_API_KEY=votre_clé_api_mistral_ici
COHERE_API_KEY=votre_clé_api_cohere_ici
LANGSMITH_API_KEY=
```

Pour surveiller votre application avec LangSmith (si vous le souhaitez) :

1. **Créer un compte LangSmith** : Allez sur [smith.langchain.com](https://smith.langchain.com)

2. **Obtenir votre clé API** : Dans les paramètres de votre compte

3. **Ajouter vos variables d'environnement**
```bash
# Configuration LangSmith
LANGSMITH_API_KEY=votre_cle_api_langsmith_ici
LANGSMITH_PROJECT=agentic_rag_multi_agent
```

4. **Lancer l'application** :
```bash
poetry run python app.py
```

## Évaluation (pertinence + avant/après)

**Lancer l'évaluation** :
```bash
uv run python evaluation/run_eval.py \
  --dataset evaluation/dataset.jsonl \
  --mode both \
  --out-dir evaluation/outputs
```
Les résultats sont dans `evaluation/outputs/` (`eval_summary.json` et `eval_results.json`).

Métriques suivies :
- Retrieval : `recall@k`, `mrr@k`, `ndcg@k`
- Réponse : `mean_f1`, `context_hit_rate`
- Vérification : `supported_rate`, `relevant_rate`

Fichiers générés :
- `eval_summary.json`
- `eval_results.json`
- `eval_regressions.json`
- `eval_errors.json`

## Évaluation FinanceBench (documents financiers difficiles)

Deuxième évaluation, sur [FinanceBench](https://github.com/patronus-ai/financebench) (Patronus AI) —
le benchmark utilisé par [Mistral pour évaluer Agentic Search](https://mistral.ai/news/agentic-search/) :
QA sur des filings SEC de 150 à 260 pages, denses en tableaux.

**Préparation (une seule fois, ~5-15 min)** — télécharge, OCRise et met en cache 3 10-K (AMD, American Express, Boeing) :
```bash
uv run python evaluation/financebench/prepare.py
```

**Lancer l'évaluation (5-10 min)** :
```bash
uv run python evaluation/financebench/run_financebench_eval.py --mode both
```

**Résultats** (21 questions, juge LLM au protocole du benchmark, stables sur plusieurs runs) :

| | Correctes | Hallucinations | Refus |
|---|---|---|---|
| Ce système (agentic) | **~71-76 %** | **~14 %** | ~10 % |
| GPT-4-Turbo + retrieval (papier FinanceBench) | ~19 % | 81 % de réponses fausses ou refusées | |
| Outils RAG juridiques commerciaux (étude Stanford) | 42-65 % | 17-33 % | |

Quand la preuve atteint le LLM, la justesse monte à ~80 % — le facteur limitant est le retrieval,
pas la génération, et l'éval le mesure : `page_hit@k` / `page_recall@k` (exacts, grâce aux pages
annotées du benchmark), `accuracy` / `hallucination_rate` / `refusal_rate` (juge LLM).

Détail du protocole, options et notes d'implémentation : [`evaluation/financebench/README.md`](evaluation/financebench/README.md).

## CI (GitHub Actions)

Workflow : `.github/workflows/eval.yml`

Secrets requis :
- `MISTRALAI_API_KEY`
- `LANGSMITH_API_KEY` (optionnel)

## Déploiement

Le projet est configuré pour déployer le frontend sur Vercel et le backend sur Railway.

### Déploiement du Backend sur Railway

1. **Créer un projet sur Railway** : https://railway.app
2. **Connecter votre repository GitHub**
3. **Configurer les variables d'environnement** :
   - `MISTRALAI_API_KEY` : Votre clé API Mistral
   - `LANGSMITH_API_KEY` : (optionnel) Votre clé API LangSmith
   - `CORS_ALLOWED_ORIGIN` : L'URL de votre frontend Vercel (ex: `https://your-app.vercel.app`)
4. **Railway détectera automatiquement** le `Dockerfile` et `railway.toml`
5. **Notez l'URL de votre backend** Railway (ex: `https://your-app.railway.app`)

### Déploiement du Frontend sur Vercel

1. **Créer un projet sur Vercel** : https://vercel.com
2. **Connecter votre repository GitHub**
3. **Configurer les variables d'environnement** :
   - `VITE_RAILWAY_API_URL` : L'URL de votre backend Railway (ex: `https://your-app.railway.app`)
4. **Vercel détectera automatiquement** le `vercel.json` et déploiera le frontend
5. **Mettre à jour CORS_ALLOWED_ORIGIN** sur Railway avec l'URL Vercel

### Structure de déploiement

- **Frontend (Vercel)** : Le répertoire `frontend/` est déployé sur Vercel
- **Backend (Railway)** : Le répertoire `backend/` est déployé sur Railway via Docker
- Les fichiers `.vercelignore` et `vercel.json` garantissent que seul le frontend est déployé sur Vercel

Ajoutez une étoile au repo pour soutenir mon travail. 🙏