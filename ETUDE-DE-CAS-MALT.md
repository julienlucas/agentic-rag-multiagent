# RAG agentique multi-agent, évalué sur FinanceBench

Un système RAG multi-agent qui répond sur des documents longs et denses en tableaux
(rapports SEC de 150 à 260 pages), avec une réponse contrainte aux seuls passages
récupérés et une citation de page à chaque affirmation. Évalué sur **FinanceBench**,
le benchmark que Mistral utilise pour mesurer son produit Agentic Search — chiffres,
intervalles de confiance et limites au complet plus bas.

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

- **2 jeux d'éval, 2 rôles distincts** — 21 questions FinanceBench (vérité terrain annotée par des experts, en anglais) portent le chiffre publiable ; 40 questions maison sur 2 rapports techniques (en français, vérité terrain rédigée par moi) servent de filet de non-régression hors domaine financier. Je ne présente pas les seconds comme un score : on ne se fait pas noter sur un examen qu'on a écrit.
- **Documents réels** — 3 rapports annuels SEC : AMD (~180 p.), American Express (260 p.), Boeing (~150 p.).
- **Index combiné** — les 3 documents indexés ensemble, le réglage difficile.
- **Retrieval exact** — pages de preuve annotées : `page_hit@k` et `page_recall@k`, sans matching flou.
- **Juge LLM** — verdict ternaire CORRECT / INCORRECT / REFUSAL, protocole officiel du papier.
- **Métrique reine** — `hallucination_rate` : un refus est gérable, une réponse fausse ne l'est pas. Publiée avec son comptage brut.
- **Comparaison honnête** — baseline et agentic partagent le même retrieval initial, donc le delta isole l'apport des agents. Avant les correctifs de la boucle corrective, il était nul (les deux modes exécutaient le même code). Après : la preuve atteint le modèle sur 17 questions au lieu de 14, et le mode agentic est au niveau ou au-dessus de la baseline à chaque run.
- **Diagnostic clé** — quand la preuve atteint le modèle, il répond juste 15 fois sur 17. Quand elle ne l'atteint pas, tout repose sur la génération contrainte. **Le goulot, c'est le retrieval**, pas la génération.
- **Coût maîtrisé** — caches OCR / chunks / embeddings : ~0,20 $ par run en 3 min, relançable à chaque commit.

**Ce que l'éval a fait changer dans le code**

- **Fusion RRF** — elle éjectait du top-10 des preuves aux rangs 2 et 6. Le top-5 initial est devenu intouchable.
- **Boucle corrective** — elle ne partait jamais : le vérificateur est biaisé vers « partiel », et le seuil de reranker censé compenser n'a jamais rien déclenché. L'éval a montré que les deux modes exécutaient le même code — le verdict du vérificateur était calculé puis jeté. Trois correctifs mesurés un par un : `PARTIAL` déclenche la correction (0 → 43 % des questions) ; les requêtes réécrites en langage naturel au lieu du booléen que produisait le modèle ; les passages ajoutés reclassés contre la question d'origine et placés **après** les 10 initiaux, jamais à leur place. Preuve transmise au modèle : 14 → 17 questions sur 21.
- **Juge LLM** — il classait « refus » toute réponse *contenant* une phrase de refus, même complète et correcte. Les 6 refus d'un run portaient sur des réponses de 300 à 1 900 caractères. Corrigé et couvert par un test : le refus doit constituer toute la réponse.
- **HyDE** — dégradait le retrieval. Désactivé malgré la hype. Idem pour la décomposition de requête : implémentés, mesurés, écartés.

## 📊 Résultats & impact

*Mesurés sur un benchmark public, pas sur des exemples choisis.*

| FinanceBench (21 questions, 3 filings SEC) | Correctes | Hallucinations |
|---|---|---|
| **Ce système** *(run du 2 sept. 2026)* | **86 %** (18/21) | 14 % (3/21) |
| RAG naïf *(papier FinanceBench, GPT-4-Turbo 2023, benchmark complet)* | ~19 % | 81 % de réponses fausses ou refusées |
| Mistral Agentic Search *(repère externe, Medium 3.5, 150 questions)* | 86 % | — |
| Outils RAG juridiques commerciaux *(étude Stanford)* | 42–65 % | 17–33 % |

Même pipeline sans les agents, sur le même run : 15/21. Le modèle n'étant pas déterministe, ce
chiffre oscille de 15 à 19 d'un run à l'autre — ce qui tient, c'est que l'agentic est au niveau ou
au-dessus à chaque run depuis les correctifs. Les trois lignes de comparaison portent sur d'autres
échantillons : des ordres de grandeur, pas un match à armes égales. Les sorties brutes sont
versionnées dans le dépôt.

- **MRR@10** — 15 % → **88 %** *(jeu interne de 40 questions, run du 3 avril 2026)*
- **recall@10** — 22 % → **59 %** *(idem — le pipeline a changé depuis, à re-mesurer)*
- **Latence** — plus de 3 min → **15–25 s** par question
- **Refus** — **0 %** sur le dernier run ; les ~10 % annoncés auparavant étaient un bug du juge

**Impact**

- **Fiabilité** — 3 réponses fausses sur 21, là où le RAG naïf du papier donne 81 % de réponses fausses ou refusées.
- **Vérifiabilité** — chaque réponse cite sa page : le métier contrôle en quelques secondes au lieu de faire confiance.
- **Temps d'analyse** — une question qui imposait de parcourir 200 pages est traitée en 15–25 s.
- **Non-régression** — ~7 min sur FinanceBench, ~11 min sur le jeu interne, pour quelques dizaines de centimes : vérifier qu'on n'a rien cassé devient une routine plutôt qu'un projet.
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
Reranking Cohere → Vérificateur de pertinence : PARTIAL →
Recherche corrective : « American Express gross profit total revenues »,
« cost of services provisions » … → 5 passages ajoutés après les 10 initiaux →
Génération contrainte : aucun passage ne parle de « gross margin » →
Explique que la métrique ne s'applique pas à un émetteur de cartes
```

**Réponse attendue par le benchmark :** *« Performance is not measured through gross
margin. »* → **verdict du juge : CORRECT, faithfulness 5/5.** Un RAG naïf, lui, va chercher
le premier chiffre de marge du document et le présenter comme la réponse.

La boucle corrective cherche vraiment (`corrective_rounds: 1`, requêtes tracées dans les
sorties), ne trouve rien de plus, et c'est la génération contrainte qui refuse d'inventer un
chiffre. Sur le jeu interne, même mécanisme sur « quel est le prix d'un abonnement DeepSeek
Pro ? » posée à un rapport technique : réécriture, rien, refus.

## ✨ Caractéristiques clés

*Ce qui rend le système exploitable en contexte professionnel.*

✅ **Anti-hallucination** — réponse contrainte aux seuls passages récupérés, refus explicite sinon.
✅ **Citations sourcées** — passage numéroté + numéro de page.
✅ **Recherche corrective** — sur `PARTIAL` et `NO_MATCH`, ajoute des passages sans jamais remplacer les initiaux.
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
