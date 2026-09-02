![RAG Agentique multi-agent Header](./static/header-b.png)

# RAG Agentique multi-agent, évalué sur FinanceBench

Ce système RAG combine un récupérateur hybride (BM25 + embeddings + reranking Cohere), un routage
par document et des agents spécialisés, sur des rapports SEC de 150 à 260 pages. Il est **mesuré**
sur [FinanceBench](https://github.com/patronus-ai/financebench), le benchmark utilisé par Mistral
pour évaluer Agentic Search : 71-81 % de réponses correctes selon le run, contre ~19 % pour le
RAG naïf du papier. Tous les chiffres cités ici sont reproductibles à partir des sorties versionnées
dans `evaluation/financebench/outputs/` — [résultats et limites](#évaluation-financebench-documents-financiers-difficiles).

## Architecture IA à la base avant améliorations

![Projet Overview](./static/project-overview.jpg)

### 1. **Agent Vérificateur de Pertinence**
Évalue si les passages récupérés répondent réellement à la question (CAN_ANSWER / PARTIAL / NO_MATCH).

### 2. **Agent de Recherche Corrective**
Si les passages sont insuffisants (`relevance != CAN_ANSWER`) **et** que le score max du reranker passe sous `CORRECTIVE_RERANK_THRESHOLD` (0,5), il réécrit la question dans le vocabulaire du document (ex. « legal battles » → *litigation*) et relance la recherche avant de répondre ou de refuser.

> ⚠️ **Ce déclencheur ne se déclenche jamais sur FinanceBench** : `corrective_rate` = 0 % sur tous les runs. Les questions classées `PARTIAL` ont un score de reranker au-dessus du seuil. L'agent est implémenté et couvert par des tests, mais ce corpus ne l'exerce pas — à recalibrer, ou à mesurer sur un corpus où le retrieval décroche vraiment.

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
uv sync
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
uv run python manage.py runserver
```

## Évaluation (pertinence + avant/après)

> ⚠️ **Les résultats versionnés dans `evaluation/outputs/` datent du 3 avril 2026** et ont été
> mesurés avec un `VerificationAgent` retiré du pipeline le 22 avril 2026. Ils ne décrivent plus
> le code de ce dépôt et ne sont conservés que comme historique : relancer la commande ci-dessous
> (~80 min) avant de citer le moindre chiffre de cette section. Les chiffres à jour sont ceux de
> l'évaluation FinanceBench, plus bas.

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
- Juge LLM : `mean_correctness`, `mean_faithfulness`, `hallucination_rate`
- Vérification : `relevant_rate` (issu du rapport du pipeline)

> `supported_rate` et le `hallucination_rate` hors juge LLM sont à `null` depuis le
> retrait du `VerificationAgent` (avril 2026) : le rapport de vérification est construit
> à partir des signaux du pipeline et ne contient plus la ligne « Supporté ». La seule
> mesure d'hallucination vivante est celle du juge LLM.

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

**Résultats** — run du 2 septembre 2026, versionné dans `evaluation/financebench/outputs/`.
21 questions, 3 filings, index combiné, juge LLM au protocole du benchmark. Comptages bruts et
IC95 (Wilson), parce qu'à 21 questions un pourcentage seul ne veut pas dire grand-chose :

| | Correctes | Hallucinations | Refus |
|---|---|---|---|
| Ce système, **avec** les agents | 71,4 % (15/21) — IC95 [50-86 %] | 28,6 % (6/21) | 0 % |
| Ce système, **sans** les agents (même retrieval, une seule génération) | 81,0 % (17/21) — IC95 [60-92 %] | 19,1 % (4/21) | 0 % |
| RAG naïf — papier FinanceBench (GPT-4-Turbo 2023, benchmark complet) | ~19 % | 81 % de réponses fausses ou refusées | |
| Mistral Agentic Search — repère externe (Medium 3.5, 150 questions) | 86 % | | |
| Outils RAG juridiques commerciaux (étude Stanford) | 42-65 % | 17-33 % | |

Les trois dernières lignes portent sur des échantillons différents du nôtre : ce sont des repères
d'ordre de grandeur, pas un match à armes égales.

### Ce que ce run dit, et ce qu'il ne dit pas

- **La boucle agentique n'est pas démontrée sur ce benchmark.** Sur ce run elle est 2 questions
  *derrière* la baseline ; sur un second run le même jour
  (`financebench_summary_2026-09-02b.json`) elle passe 1 question *devant* (baseline 16/21,
  agentic 16/20). L'écart change de signe d'un run à l'autre : à 21 questions, c'est du bruit.
  Ce qui porte le résultat, c'est le retrieval hybride + reranking et la génération contrainte,
  pas la couche multi-agent.
- **La recherche corrective ne s'est déclenchée sur aucune question**, dans aucun run
  (`corrective_rate` = 0 %). Elle exige `relevance != CAN_ANSWER` **et** un score de reranker
  max < 0,5 ; les 8-9 questions classées `PARTIAL` ont toutes un score au-dessus du seuil. Elle
  est implémentée et testée, elle n'est pas exercée par ce corpus.
- **Les 2 questions perdues par le mode agentic sont toutes les deux classées `PARTIAL`** par le
  vérificateur de pertinence, avec la preuve pourtant transmise au modèle. Le signal `PARTIAL`
  dégrade la réponse sans déclencher la correction censée le compenser : c'est le prochain
  correctif à mesurer.
- **Le facteur limitant reste le retrieval.** La preuve n'atteint le modèle que dans 66,7 % des
  cas ; quand elle l'atteint, la justesse est de 92,9 % (baseline) / 78,6 % (agentic).
  L'éval le mesure directement : `page_hit@k` / `page_recall@k`, exacts grâce aux pages annotées.

> Le `refusal_rate` des runs antérieurs au 2 septembre 2026 (~10 %) était un artefact : le juge
> classait `REFUSAL` toute réponse *contenant* une des phrases de refus du pipeline, y compris au
> milieu d'une réponse complète et correcte. Corrigé — le refus doit désormais constituer toute
> la réponse. Les 6 verdicts `REFUSAL` du run précédent portaient sur des réponses de 300 à
> 1 900 caractères ; après correction, le taux de refus est de 0 %.

Détail du protocole, options et notes d'implémentation : [`evaluation/financebench/README.md`](evaluation/financebench/README.md).

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