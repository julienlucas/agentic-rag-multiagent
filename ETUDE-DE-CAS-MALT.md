# RAG agentique anti-hallucinations, évalué sur FinanceBench

Un système RAG multi-agent qui répond avec précision sur des documents longs et
denses en tableaux (rapports SEC de 150 à 260 pages) — et qui refuse plutôt que
d'inventer. Évalué sur **FinanceBench**, le benchmark que Mistral utilise pour
mesurer son produit Agentic Search.

Code : github.com/julienlucas/agentic-rag-multiagent

---

## ❌ Le problème

*Pourquoi un RAG classique décroche sur un rapport annuel de 200 pages.*

- **Documents hostiles** — 200 pages, réponse enfouie dans un tableau, le même chiffre répété partout.
- **Hallucinations** — les modèles généralistes lisent la mauvaise ligne et répondent avec assurance.
- **Vocabulaire décalé** — on demande « legal battles », le document dit *litigation*.
- **Plusieurs documents** — trouver le bon passage du bon rapport, sans savoir lequel porte la réponse.
- **Aucune mesure** — sans éval, « améliorer le RAG » c'est empiler des techniques à l'aveugle.

## ✅ La solution

*Un agent par point de blocage, et une évaluation pour arbitrer.*

- **OCR + chunking parent-child** — tableaux préservés : petits chunks pour matcher, gros pour répondre.
- **Génération contrainte** — réponse limitée aux passages récupérés, refus explicite sinon.
- **Recherche corrective** — réécrit la question dans le vocabulaire du document et relance.
- **Routage par document** — cible le bon rapport avant de chercher.
- **Recherche hybride + reranking** — BM25 pour les montants exacts, vecteurs pour le sens, Cohere pour trancher.
- **Harness d'évaluation** — chaque changement doit prouver son gain sur un benchmark public.

## 🔬 L'évaluation de ce RAG

*Posée avant de toucher au pipeline : chaque changement a dû prouver son gain.*

- **2 jeux d'éval** — 40 questions sur corpus technique, puis 21 sur FinanceBench.
- **Documents réels** — 3 rapports annuels SEC : AMD (~180 p.), American Express (260 p.), Boeing (~150 p.).
- **Index combiné** — les 3 documents indexés ensemble, le réglage difficile.
- **Retrieval exact** — pages de preuve annotées : `page_hit@k` et `page_recall@k`, sans matching flou.
- **Juge LLM** — verdict ternaire CORRECT / INCORRECT / REFUSAL, protocole officiel du papier.
- **Métrique reine** — `hallucination_rate` : un refus est gérable, une réponse fausse ne l'est pas.
- **Comparaison honnête** — baseline et agentic partagent le même retrieval : le delta isole l'apport des agents.
- **Diagnostic clé** — la preuve n'atteint le modèle que dans 67 % des cas ; quand elle l'atteint, 80 % de justesse. **Le goulot, c'est le retrieval.**
- **Coût maîtrisé** — caches OCR / chunks / embeddings : ~0,20 $ par run en 3 min, relançable à chaque commit.

**Ce que l'éval a fait changer dans le code**

- **Fusion RRF** — elle éjectait du top-10 des preuves aux rangs 2 et 6. Le top-5 initial est devenu intouchable.
- **Boucle corrective** — elle ne partait jamais : le vérificateur est biaisé vers « partiel ». Ajout d'un déclencheur sur le score du reranker.
- **HyDE** — dégradait le retrieval. Désactivé malgré la hype. Idem pour la décomposition de requête : implémentés, mesurés, écartés.

## 📊 Résultats & impact

*Mesurés sur un benchmark public, pas sur des exemples choisis.*

| FinanceBench (21 questions, filings SEC) | Correctes | Hallucinations |
|---|---|---|
| **Ce système** | **76 %** | **14 %** |
| RAG naïf *(baseline publiée dans le papier FinanceBench)* | ~19 % | 81 % de réponses fausses ou refusées |
| Outils RAG juridiques commerciaux *(étude Stanford)* | 42–65 % | 17–33 % |

- **MRR@10** — 15 % → **88 %**
- **recall@10** — 22 % → **59 %**
- **Hallucinations** — 12,5 % → **2,5 %**
- **Latence** — plus de 3 min → **15–25 s** par question

**Impact**

- **Fiabilité** — 14 % d'hallucinations, là où un RAG naïf donne 81 % de réponses fausses ou refusées.
- **Vérifiabilité** — chaque réponse cite sa page : le métier contrôle en quelques secondes au lieu de faire confiance.
- **Temps d'analyse** — une question qui imposait de parcourir 200 pages est traitée en 15–25 s.
- **Non-régression** — ~0,20 $ et 3 min par run d'éval : vérifier qu'on n'a rien cassé devient une routine.
- **Diagnostic actionnable** — on sait où le pipeline perd (le retrieval), donc où investir le budget suivant.
- **Architecture réutilisable** — changer de corpus (juridique, technique, RH) ne change pas le pipeline.

## ⚙️ Architecture

*Trois agents spécialisés au-dessus d'un retriever hybride.*

- **3 agents LangGraph** — vérificateur de pertinence → recherche corrective → génération.
- **Vérificateur** — les passages récupérés permettent-ils de répondre ? (Mistral Small)
- **Recherche corrective** — réécrit la question dans le vocabulaire du document et relance.
- **Génération** — contrainte aux seuls passages récupérés, avec citations. (Mistral Large)
- **Retriever hybride** — BM25 + embeddings 50/50, routage par document, chunking parent-child.
- **Reranking Cohere** — le plus gros gain du projet.

## 🔁 Exemple de flux d'agent

*Une question piège du benchmark, et le chemin que le système emprunte.*

**Question :** *« What drove gross margin change for American Express in FY2022? »*
— une question à réponse négative : la marge brute n'a aucun sens pour un émetteur
de cartes. C'est un piège à hallucination.

```
Routage vers le 10-K American Express → Recherche hybride BM25 + vecteurs →
Reranking Cohere → Aucun passage ne parle de « gross margin » →
Réécriture de la question dans le vocabulaire du filing → Toujours rien →
Refus d'inventer un chiffre → Explique que la métrique ne s'applique pas
à un émetteur de cartes
```

**Réponse attendue par le benchmark :** *« Performance is not measured through gross
margin. »* → **verdict du juge : CORRECT.** Un RAG naïf, lui, va chercher le premier
chiffre de marge du document et le présenter comme la réponse.

## ✨ Caractéristiques clés

*Ce qui rend le système exploitable en contexte professionnel.*

✅ **Anti-hallucination** — réponse contrainte aux seuls passages récupérés, refus explicite sinon.
✅ **Citations sourcées** — passage numéroté + numéro de page.
✅ **Recherche corrective** — relancée uniquement quand le retrieval a raté.
✅ **Réécriture de requête** — « legal battles » → *litigation*.
✅ **Routage par document** — cible le bon rapport avant de chercher.
✅ **Recherche hybride** — BM25 + vecteurs, pour les montants et noms exacts.
✅ **Tableaux préservés** — de l'OCR jusqu'à la réponse.
✅ **15–25 s par question** — Large pour la génération, Small pour les sous-agents.
✅ **Résilient en prod** — timeouts, retries, backoff sur rate limit.
✅ **Config mesurée** — chaque paramètre justifié par une éval.

## 🛠️ Stack technique

*Modèles Mistral de bout en bout, reranking Cohere, déploiement Railway + Vercel.*

| Composant | Technologie |
|---|---|
| **Orchestration multi-agents** | LangGraph (StateGraph, routage conditionnel) |
| **Framework** | LangChain |
| **LLM — génération** | Mistral Large |
| **LLM — sous-agents** (pertinence, routage, réécriture) | Mistral Small |
| **OCR** | Mistral OCR (batché, reprise sur rate limit) |
| **Embeddings** | Mistral Embed |
| **Reranking** | Cohere Rerank v4 Pro (multilingue) |
| **Recherche lexicale** | BM25 (`rank-bm25`) |
| **Base vectorielle** | Chroma |
| **Chunking** | Parent-child (1200 / 400) |
| **Backend** | Python 3.12, Django, LangChain |
| **Frontend** | React, TypeScript, Vite, Tailwind |
| **Observabilité** | LangSmith |
| **Déploiement** | Railway (backend, Docker) + Vercel (frontend) |
| **Évaluation** | Harness maison + juge LLM calibré (protocole FinanceBench) |

## 🚀 Transposable à

*Le même pipeline s'applique à tout corpus documentaire dense.*

- **Analyse financière** — rapports annuels, due diligence, reporting.
- **Juridique & conformité** — contrats, réglementaire, veille normative.
- **Documentation technique** — normes, specs, manuels de maintenance.
- **Appels d'offres** — recherche dans l'historique et la base de connaissance.
- **Audit d'un RAG existant** — poser l'éval, identifier où le pipeline perd, chiffrer chaque correctif.
