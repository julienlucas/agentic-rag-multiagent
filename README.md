# RAG Agentique multi-agent évalué sur FinanceBench
![RAG Agentique multi-agent Header](./static/header-b.png)

Si vous appréciez, ajoutez une ⭐ au repo pour soutenir mon travail. 🙏

Ce système RAG combine un récupérateur hybride (BM25 + embeddings + reranking Cohere), un routage
par document et des agents spécialisés, sur des rapports SEC de 150 à 260 pages. Il est **mesuré**
sur [FinanceBench](https://github.com/patronus-ai/financebench), le benchmark utilisé par Mistral
pour évaluer Agentic Search : **83,3 % de réponses correctes** (20/24) sur le run versionné,
contre ~19 % pour le RAG naïf du papier. Tous les chiffres cités ici sont
reproductibles à partir des sorties versionnées dans `evaluation/financebench/outputs/` —
[résultats et limites](#évaluation-financebench-documents-financiers-difficiles).

## Architecture IA à la base avant améliorations

![Projet Overview](./static/project-overview.jpg)

### 1. **Agent Vérificateur de Pertinence**
Évalue si les passages récupérés répondent réellement à la question (CAN_ANSWER / PARTIAL / NO_MATCH). Son verdict ne bloque plus la génération : il est transmis au modèle de réponse comme indice (« le contexte initial a été jugé partiel, cherchez ce qui manque »).

### 2. **Agent de Recherche et de réponse, avec outils**
Le modèle de génération reçoit les 10 meilleurs passages et les [trois outils](#les-outils) décrits plus bas. Il répond directement si le contexte suffit ; sinon il cherche — en voyant chaque résultat avant de décider du suivant, 5 appels au plus — et répond **dans la même conversation** : le modèle qui cherche est celui qui répond, comme dans l'[Agentic Search](https://mistral.ai/news/agentic-search/) de Mistral. Les outils sont disponibles sur **toutes** les questions ; le mode conditionnel (agent de recherche séparé, ou réécriture de la question) reste disponible pour comparaison via `GENERATOR_TOOLS_ENABLED` et `CORRECTIVE_MODE`.

### 3. **Génération contrainte**
La réponse ne s'appuie que sur les passages numérotés — initiaux ou ramenés par les outils — avec une citation `[n]` après chaque affirmation, et refuse quand l'information n'y est pas. Deux règles de prompt tirées des runs FinanceBench : un ratio ou une marge dont les composantes sont dans le contexte se **calcule** (formule, chiffres cités, résultat) ; et « non disponible » ne s'écrit qu'après un `grep` sans résultat.

## Cet agent a des outils à dispo

Trois opérations façon système de fichiers, données au modèle de réponse. Les pages OCR sont conservées entières (`backend/retriever/page_store.py`) à côté des chunks : les chunks servent à *trouver*, les pages à *lire*.

| Outil | Ce qu'il fait |
|---|---|
| `search(query, doc)` | Le retrieval hybride du pipeline (BM25 + vecteurs, routage, rerank Cohere), relancé avec une nouvelle requête, optionnellement restreint à un document. Renvoie 8 extraits avec document et page. |
| `grep(pattern, doc)` | Occurrences littérales d'un motif (regex, insensible à la casse), page par page, sur tout le document. Exhaustif : 0 résultat permet d'affirmer qu'un terme n'y figure pas. |
| `read_page(doc, page, end_page)` | La page entière telle que l'OCR l'a produite, tableau compris — ce qu'un chunk de 1 200 caractères ne montre jamais. `end_page` lit 2 à 3 pages d'un coup pour un tableau à cheval. |

Chaque passage ramené par un outil reçoit un numéro `[n]`, affiché dans le résultat, que la réponse cite comme les autres. Les 10 passages initiaux gardent leurs numéros : les outils ne peuvent qu'**ajouter** après eux. Le rapport de vérification renvoyé avec chaque réponse liste les appels effectués.

### Le système inclut un retriever hybride pour maximiser la pertinence
- **Algo BM25 + Embeddings** : Recherche texte classique à forte précision lexicale + Recherche sémantique capturant le sens contextuel. L'index vectoriel déclare explicitement sa métrique (`VECTOR_SPACE = "cosine"`) : le défaut de Chroma est `l2`, qui n'est correct que tant que les embeddings sont normés.
- **Routage par document** : avant de chercher, le système cible le(s) document(s) que la question désigne (nom d'entreprise ou de fichier) — indispensable quand plusieurs documents longs sont indexés ensemble.
- **Reranking Cohere + parent-child + multi-query** : petits chunks pour matcher, gros chunks pour répondre.

## Stack de modèles
- ⚡ Mistral OCR
- 🧠 Mistral Embed (embeddings)
- 🧠 Cohere Rerank v4 Pro multi-langue
- 💎 Mistral Large (recherche à outils + génération) + Mistral Small (sous-agents : pertinence, routage, multi-query)

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
```

Pour surveiller votre application avec LangSmith (si vous le souhaitez) :

1. **Créer un compte LangSmith** : Allez sur [smith.langchain.com](https://smith.langchain.com)

2. **Obtenir votre clé API** : Dans les paramètres de votre compte

3. **Ajouter vos variables d'environnement**
```bash
# Configuration LangSmith pour le monitoring
LANGSMITH_API_KEY=votre_cle_api_langsmith_ici
LANGSMITH_PROJECT=agentic_rag_multi_agent
```

4. **Lancer l'application** :
```bash
uv run python manage.py runserver
```

## Évaluation FinanceBench (documents financiers difficiles)

L'évaluation, sur [FinanceBench](https://github.com/patronus-ai/financebench) (Patronus AI) —
le benchmark utilisé par [Mistral pour évaluer Agentic Search](https://mistral.ai/news/agentic-search/) :
QA sur des filings SEC de 150 à 260 pages, denses en tableaux.

**Préparation, l'indexation des documents (une seule fois, ~10-20 min)** — télécharge, OCRise et met en cache 4 10-K (AMD, American Express, Boeing, PepsiCo) :
```bash
uv run python evaluation/financebench/prepare.py
```

**Lancer l'évaluation (5-10 min)** :
```bash
uv run python evaluation/financebench/run_financebench_eval.py --mode both
```

**Résultats** — run du 4 septembre 2026 (soir), versionné dans `evaluation/financebench/outputs/`.
26 questions, 4 filings, index combiné, juge LLM au protocole du benchmark, comptages bruts :

| | Correctes | Hallucinations | Refus |
|---|---|---|---|
| Mistral Agentic Search — repère externe (Medium 3.5, 150 questions) | 86 % | | |
| Ce RAG, **avec** les agents (modèle de réponse équipé des outils) | **83,3 % (20/24)** | 16,7 % (4/24) | 0 |
| Ce RAG, **sans** les agents (même retrieval, une seule génération) | 65,4 % (17/26) | 26,9 % (7/26) | 2 |
| Outils RAG juridiques commerciaux (étude Stanford) | 42-65 % | 17-33 % | |
| RAG naïf — papier FinanceBench (GPT-4-Turbo 2023, benchmark complet) | ~19 % | 81 % de réponses fausses ou refusées | |

Les lignes Mistral, Stanford et papier FinanceBench portent sur des échantillons différents de ce RAG : ce sont des repères d'ordre de grandeur, pas un match à armes égales.

Détail du protocole, options et notes d'implémentation : [`evaluation/financebench/README.md`](evaluation/financebench/README.md).
