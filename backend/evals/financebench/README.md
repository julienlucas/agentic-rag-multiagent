# Évaluation FinanceBench

Évaluation du RAG agentique sur des filings SEC longs et denses en tableaux — le seul jeu
d'éval du projet, et le seul qui porte un chiffre publiable (annotation experte externe).

## Pourquoi FinanceBench

[FinanceBench](https://github.com/patronus-ai/financebench) (Islam et al., 2023, Patronus AI) est
le benchmark que **Mistral a utilisé pour évaluer son produit Agentic Search**
([annonce](https://mistral.ai/news/agentic-search/)) : QA financière sur des filings SEC (10-K,
10-Q, 8-K) longs et denses en tableaux — ~147 pages par document en moyenne. Mistral y annonce
un passage de **26,7 % à 86 %** de correctness avec Agentic Search, jugé par un LLM calibré sur
des annotations humaines.

Ce que le benchmark met en difficulté et que les documents précédents ne testaient pas :

- **Densité** : un 10-K fait 150 à 260 pages, contre ~30 pages pour les documents précédents.
- **Tableaux** : les réponses se trouvent dans des états financiers consolidés, pas dans du texte
  narratif — l'OCR et le chunking doivent les préserver.
- **Distracteurs** : chaque chiffre apparaît des dizaines de fois dans le document (exercices
  différents, segments différents, notes annexes).
- **Questions à réponse négative** : plusieurs questions attendent « il n'y en a pas » ou
  « cette métrique ne s'applique pas à cette entreprise » — un piège à hallucination.

> ⚠️ À ne pas confondre avec [`yuweiyin/FinBench`](https://huggingface.co/datasets/yuweiyin/FinBench),
> un dataset de **classification tabulaire** (défaut / fraude / churn) qui ne contient aucune
> question et n'est pas un benchmark de RAG.

## Sous-ensemble évalué

Le corpus complet fait 705 Mo (368 PDF, ~53 900 pages). On évalue les **3 documents portant
7 questions chacun**, plus PepsiCo pour un signal numérique exact (réponses de type `$9068.00`),
soit **26 questions** :

| Document | Questions | PDF | Pages |
|---|---|---|---|
| `AMD_2022_10K` | 7 | 5,1 Mo | ~120 |
| `AMERICANEXPRESS_2022_10K` | 7 | 2,4 Mo | 260 |
| `BOEING_2022_10K` | 7 | 1,4 Mo | ~150 |
| `PEPSICO_2022_10K` | 5 | | 503 |

Répartition : 17 `domain-relevant` + 7 `novel-generated` + 2 `metrics-generated`, mêlant
extraction d'information, raisonnement numérique et raisonnement logique.

Les questions vivent **uniquement dans LangSmith** (dataset « agentic-search · FinanceBench » : question, réponse de
référence, pages et passages de preuve, mots-clés), écrit par `prepare.py` et lu par les expériences.

Les 4 documents sont indexés **dans un seul index** : le système doit retrouver le bon passage
du bon document, sans savoir lequel porte la réponse. `--per-doc` donne le réglage plus
facile (un index par document).

Les runs antérieurs au 4 septembre 2026 (après-midi) portaient sur les 3 premiers documents,
21 questions : leurs chiffres ne sont pas comparables à ceux d'un run à 26.

### Jeu étendu (70 questions)

À 26 questions, l'IC95 de l'accuracy fait ~35 points de large : un écart de 5 points entre deux
versions n'y est pas mesurable. `--docs extended` prend tous les documents qui portent au moins
3 questions : **18 documents, 70 questions**. Il s'écrit dans un dataset LangSmith à part,
« agentic-search · FinanceBench (extended) », jamais dans « agentic-search · FinanceBench » (le protocole publié) :

```bash
uv run python backend/evals/financebench/prepare.py --docs extended
uv run python backend/evals/experiment.py --mode both --dataset "agentic-search · FinanceBench (extended)"
```

La préparation OCRise 14 documents de plus. Coût estimé, pas mesuré : de l'ordre de 2 000 pages,
soit ~8 $ d'OCR à la grille de `cost.py`. Un run complet coûte environ 70/26 fois celui du
protocole à 26 questions.

### Corpus complet : 84 documents, 150 questions

Les 150 questions open source portent sur **84 documents** (64 10-K, 8 10-Q, 6 earnings, 6 8-K) ;
52 documents n'en portent qu'une. Deux préréglages de `--docs` s'ajoutent à `extended` :

| Préréglage | Documents | Questions | Dataset LangSmith |
|---|---|---|---|
| `pilot` | les 20 qui portent le plus de questions (dont les 4 du protocole) | 65 sur 74 | « agentic-search · FinanceBench (pilot 20) » |
| `all` | les 84 | 139 sur 150 | « agentic-search · FinanceBench (84 docs) » |

Les questions retirées ont une preuve sur une page absente du texte indexé (voir ci-dessous).

Le corpus complet fait **12 013 pages** (179 134 chunks) indexées ensemble dans un seul espace
Qdrant ; le pilote, 3 048 pages (43 493 chunks).

**Résultats du 12 octobre 2026** (Claude Sonnet 4.6, juge Qwen3 235B, avec outils) : **88,1 %** sur le
corpus complet (119 / 135 questions jugées ; 4 bloquées par le quota Bedrock) et **92,3 %** sur le pilote
(60 / 65). Sans outils, sur le pilote : 53,8 %. Détail, ablation et coût : README principal,
« Évaluation FinanceBench ».

**Références corrigées.** Deux réponses de référence de FinanceBench sont fausses, vérifié dans le
document : elles sont corrigées par `REFERENCE_CORRECTIONS` (`prepare.py`), la référence d'origine
restant lisible dans la justification.

| Question | Référence FinanceBench | Corrigée |
|---|---|---|
| `financebench_id_00283` — reste à payer pour la séparation d'Upjohn | 77,78 (700/9) | 70 (10 % de 700 M$) |
| `financebench_id_02419` — Pfizer scinde-t-il un segment au T2 2023 ? | Oui, Upjohn | Non : scission faite le 16 nov. 2020 |

### Source du texte : markdown recalé sur le PDF (par défaut)

OCRiser les 84 documents (~12 000 pages) coûterait ~48 $. Le texte vient donc par défaut du dataset
Hugging Face [`shhdwi/financebench-markdown`](https://huggingface.co/datasets/shhdwi/financebench-markdown),
un markdown OCR des 84 documents de même qualité que Mistral OCR (texte, chiffres, tableaux structurés),
mais qui pose trois problèmes, traités par `markdown_corpus.py` :

- **Pas de pagination.** Ses balises `<page_number>` reprennent les numéros imprimés (table des
  matières comprise), pas les pages du PDF où sont annotées les preuves. Chaque bloc (paragraphe,
  ligne de tableau) est rattaché à la page du PDF dont le texte, extrait par pypdf, contient ses
  n-grammes, sans jamais reculer d'une page. Validé sur les 4 documents du protocole contre les
  pages de Mistral OCR : 99 à 100 % des blocs à la même page.
- **Des doublons.** Le markdown recopie souvent une page juste après elle-même (la moitié des
  paragraphes longs d'AMD 2022). Un bloc déjà présent sur sa page n'y est pas répété : le volume
  retombe sur celui de Mistral OCR (421 k caractères contre 426 k pour AMD).
- **Des pages manquantes** : ~6 % des pages du corpus (764 sur 12 013), dont des pages de preuve.
  Par défaut (`--fill none`), elles restent vides et **les questions dont une preuve y tombe sont
  retirées du dataset** (11 sur 150) : insolubles pour tout RAG, elles ne mesureraient rien. Le
  dataset du protocole publié (26 questions) n'est jamais élagué. `--fill ocr` passe ces pages à
  Mistral OCR, ainsi que les pages scannées (~900 pages, ~3,60 $) ; `--fill pdf-text` les comble
  avec le texte brut du PDF (gratuit, tableaux aplatis).

Les tableaux HTML sont rendus en tableaux markdown, le format de Mistral OCR. Chaque chunk porte
`pdf_url`, le PDF annoté de Patronus AI (copie GitHub), à ouvrir à la page `page + 1`.

Avant les embeddings, `prepare.py` vérifie que chaque preuve annotée se retrouve dans le texte à sa
page (±1) et liste les preuves introuvables. `--skip-embeddings` s'arrête là, sans appel Bedrock.
Sur les 84 documents, 11 preuves restent signalées : leur texte est présent, mais recopié d'un
tableau sous une autre forme (elles ne correspondent pas mieux au texte brut du PDF).

**Tableaux corrompus dans le markdown.** Certains tableaux du markdown shhdwi sont décalés d'une
ligne : sur la page de garde du 10-Q T2 2023 de 3M, la note 2026 se retrouvait cotée au Chicago Stock
Exchange, et dans le tableau de croissance organique du 10-K 2022 de 3M, chaque segment portait le
chiffre du suivant. Un document listé dans `FULL_OCR_DOCS` (`prepare.py`) est OCRisé en entier par
Mistral OCR, même en source markdown (aujourd'hui `3M_2023Q2_10Q`, 92 pages, ~0,37 $). Après l'ajout
d'un document à la liste, `--reindex DOC` le ré-indexe dans un espace qui le contient déjà : l'ancienne
version est remplacée, et une copie depuis un autre espace remplace aussi la sienne.

`--source ocr` reprend l'ancien chemin (Mistral OCR de tout le PDF). Chaque source a son propre
espace Qdrant : passer la même option `--source` à `experiment.py`.

```bash
uv run python backend/evals/financebench/prepare.py --docs pilot --skip-embeddings  # contrôle, sans embeddings
uv run python backend/evals/financebench/prepare.py --docs pilot                    # indexation (Cohere Embed v4)
uv run python backend/evals/experiment.py --mode both --dataset "agentic-search · FinanceBench (pilot 20)"
```

## Prérequis

Un fichier `.env` à la racine du projet :

```bash
MODEL_PROVIDER=bedrock  # Claude, embeddings, rerank (Cohere 3.5 à Francfort) et juges sur Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
MISTRALAI_API_KEY=...   # seulement pour --source ocr ou --fill ocr
LANGSMITH_API_KEY=...   # optionnel
```

## Lancer l'évaluation

L'évaluation se fait en deux temps, parce que le coût dominant est l'ingestion (~1 070 pages à
OCRiser), pas les questions.

```bash
# 1) Préparation — une seule fois (~10-20 min). Télécharge, OCRise, indexe dans Qdrant,
#    écrit le dataset dans LangSmith ; --clean supprime ensuite PDF et cache locaux.
uv run python backend/evals/financebench/prepare.py --clean

# 2) Le run évalué — cible 5-10 min, reproductible
uv run python backend/evals/experiment.py --mode both
```

La préparation met en cache les pages (`cache/*.markdown.json`, `cache/*.ocr.json`) et les chunks
(`cache/*.<source>.chunks.pkl`), puis indexe chunks, embeddings et pages dans les **collections d'évaluation de Qdrant**
(`eval_chunks` / `eval_pages`), séparées de celles des utilisateurs (`chunks` / `pages`). Les
expériences lisent uniquement cet index. Le cache local (`cache/`) n'est qu'un intermédiaire de
`prepare.py`, supprimable une fois l'index écrit (`--clean`) ; seul `--per-doc` en a besoin. Relancé,
`prepare.py` saute les rapports déjà présents dans l'index Qdrant : rien n'est repayé. Prérequis et
détail des étapes : README principal, « Récupérer et indexer le jeu d'évaluation ». PDF (retéléchargeables) et caches sont gitignorés. Aucun résultat n'est
écrit en local : tout part dans LangSmith (voir « Sorties »).

### Options utiles

| Flag | Effet |
|---|---|
| `--dataset NOM` | Dataset LangSmith évalué : « agentic-search · FinanceBench (pilot 20) », « … (84 docs) »… |
| `--mode baseline\|agentic\|both` | Défaut `both` (mesure l'apport de la boucle agentique) |
| `--ids ID1,ID2` | Seulement ces questions (`financebench_id`), sur l'index du corpus entier : relancer les échecs d'un run pour quelques dizaines de centimes |
| `--workers N` | Questions en parallèle (défaut 3). **Passer à 1 avec une clé Cohere trial** (~10 req/min) |
| `--max-items N` | Limite le nombre de questions (test rapide) |
| `--no-judge` | Désactive le juge LLM (pas de métriques d'accuracy) |
| `--reps N` | Rejoue la génération N fois par question (retrieval une seule fois) : ajoute exactitude moyenne, pass^k et stabilité du verdict. Les métriques du protocole restent calculées sur la 1re répétition. Coût × N |
| `--time-budget S` | Arrêt propre au-delà de S secondes, avec résultats partiels (défaut 600 ; **0 = sans limite**, nécessaire au-delà de ~45 questions) |
| `--per-doc` | Un index par document au lieu de l'index combiné |
| `--page-tolerance N` | Écart de pagination toléré entre PDF annoté et OCR (défaut 1) |
| `--verbose` | N'étouffe pas les logs de debug du pipeline |

### Si l'ingestion tape un rate limit (HTTP 429)

L'OCR d'un 10-K de 260 pages consomme beaucoup de quota d'un coup. `prepare.py` rejoue
automatiquement avec un backoff exponentiel (jusqu'à 7 tentatives, en respectant l'en-tête
`Retry-After`), découpe l'OCR en lots de 50 pages et **écrit le cache après chaque lot** :
une interruption ne fait jamais perdre des pages déjà payées, et relancer la commande reprend
exactement là où ça s'était arrêté.

Si les 429 persistent, réduisez la pression :

```bash
uv run python backend/evals/financebench/prepare.py --ocr-batch 20 --ocr-delay 10
```

Et si besoin, ingérez un document à la fois :

```bash
uv run python backend/evals/financebench/prepare.py --docs AMD_2022_10K
uv run python backend/evals/financebench/prepare.py --docs AMERICANEXPRESS_2022_10K
uv run python backend/evals/financebench/prepare.py --docs BOEING_2022_10K
uv run python backend/evals/financebench/prepare.py --docs PEPSICO_2022_10K
uv run python backend/evals/financebench/prepare.py   # assemble et construit l'index
```

## Métriques

### Protocole FinanceBench (comparable au chiffre public de Mistral)

Chaque réponse reçoit un verdict ternaire d'un juge LLM, Qwen3 235B sur Bedrock à Francfort
(`EVAL_JUDGE_MODEL_ID`, `EVAL_JUDGE_REGION`) : hors famille Claude, il ne note donc pas sa
propre famille. Il est calibré sur annotation humaine (voir « Calibrer le juge » ci-dessous).
Son prompt suit le protocole FinanceBench : même information que la référence, à la
formulation, à l'unité et à l'arrondi près.

Historique du juge, dont les verdicts ne se comparent pas d'un juge à l'autre :
`mistral-large-latest` (API Mistral) jusqu'au 3 octobre 2026, Pixtral Large 25.02 (Bedrock)
jusqu'au 11 octobre 2026, puis Qwen3 235B.

#### Calibrer le juge

Sur les mêmes 65 réponses de l'essai (11 octobre 2026), Pixtral Large donne
83,1 %, gpt-oss-120b 70,8 % et Qwen3 235B 69,2 % : le choix du juge pèse plus que bien des
changements du système. Un juge se choisit donc sur son accord avec une annotation humaine,
pas sur le score qu'il donne :

```bash
# File d'annotation LangSmith, à l'aveugle : les réponses où les juges divergent d'abord
uv run python backend/evals/financebench/annotation.py queue --experiment "<expérience agentic>" --size 30
# Après annotation (clé human_correct) : accord de chaque juge candidat avec l'humain
uv run python backend/evals/financebench/annotation.py agreement --project "<projet d'annotation>"
# Annotations → exemples du juge (judge_examples.json, versionné)
uv run python backend/evals/financebench/annotation.py examples --project "<projet d'annotation>"
```

Ce que le juge reçoit, en plus de la question, de la référence et de la réponse :

- **Les réponses annotées comme exemples** (`judge_examples.json`), verdict et commentaire de
  l'annotateur compris, **sauf celle de la question qu'il note** : sinon il recopierait le verdict
  humain, et l'accord mesuré par `agreement` ne vaudrait plus rien. Un commentaire qui dit *pourquoi*
  pèse plus qu'un verdict seul.
- **Une rubrique au critère de l'annotateur** : CORRECT si l'élément demandé est présent et les
  chiffres cités justes (écart d'arrondi ≤ 1 %) ; une granularité différente, plus de précision ou un
  détail secondaire inexact ne rendent pas faux ; INCORRECT pour un mauvais chiffre, un autre élément,
  une conclusion inverse, ou une question fermée sans Oui / Non tranché.
- **Une grille à remplir avant le verdict** (élément demandé, présent, chiffres justes, question
  fermée tranchée) : le verdict en découle, au lieu d'une comparaison d'un bloc avec la référence.
- **Les passages cités par la réponse en premier**, sur 16 000 caractères : coupé à 6 000 dans
  l'ordre de récupération, le contexte perdait les pages lues par les outils, et le juge prenait des
  chiffres présents dans le document pour des inventions.

**Contrôle numérique.** Quand la référence est un nombre seul (9 questions sur 65 dans le pilote),
le calcul tranche : si les deux premières lignes de la réponse contiennent la même valeur, à
l'arrondi de la référence ou à 1 % près, éventuellement à une autre échelle (millions / milliards,
ratio / pourcentage), le verdict est CORRECT. Seulement dans ce sens : une valeur exprimée autrement
reste à l'appréciation du juge.

Mesuré sur les 10 réponses annotées le 11 octobre : le juge reste plus strict que l'annotateur sur
2 à 3 réponses justes sur le fond (granularité, détail secondaire), et n'en valide jamais une fausse.
Il varie d'un run à l'autre sur ces cas limites : il faut davantage d'annotations commentées pour
le stabiliser.

- **`accuracy`** — réponses `CORRECT` (tolérante aux écarts de format, d'unité et d'arrondi).
- **`hallucination_rate`** — réponses `INCORRECT` : le système répond avec assurance **et** se
  trompe. C'est la métrique centrale du papier — le risque réel en usage professionnel.
- **`refusal_rate`** — réponses `REFUSAL` : le système déclare ne pas savoir. Un refus n'est pas
  une bonne réponse, mais il n'est pas dangereux.

Chaque taux est publié avec son **comptage brut** (`counts`) et son **intervalle de confiance à
95 %** (Wilson, `*_ci95`), et le tableau de synthèse les affiche.

> ⚠️ **Peu de questions, c'est du bruit.** L'IC95 d'une accuracy autour de 85 % fait environ
> **30 points de large sur 26 questions, 17 sur 65 et 11 sur 135** : d'un run à l'autre sur le même code,
> le pilote a varié de 72 à 83 %. Comparer deux runs question par question (gagnées / perdues), pas sur
> le seul pourcentage. Une différence d'une ou deux questions entre
> deux configurations n'est pas une amélioration, c'est du bruit — le run l'écrit explicitement en
> fin de rapport. Ne citer un gain que s'il tient sur plusieurs questions **et** que les intervalles
> ne se recouvrent quasiment plus.

Les IC95 (Wilson) sont calculés et affichés dans le tableau de fin de run.

Les refus sont détectés **sans appel LLM** quand le pipeline renvoie un de ses messages figés
(`backend/agents/research_agent.py`, `backend/agents/workflow.py`), ce qui économise du budget.
Les erreurs techniques (timeout, LLM indisponible) sont comptées à part et exclues du
dénominateur, pour ne pas les confondre avec des refus.

### Faithfulness et answer relevancy

- **`mean_faithfulness`** (1-5) — note donnée par le juge dans le même appel que le verdict : la
  réponse s'en tient-elle aux extraits fournis ? Ce n'est pas la faithfulness de RAGAS
  (vérification affirmation par affirmation), mais un signal global.
- **`mean_answer_relevancy`** (0-1) — la réponse traite-t-elle la question posée ? Méthode RAGAS
  (`backend/evals/experiment_utils.py`) : Ministral 3 14B (Bedrock, eu-west-1, `EVAL_RELEVANCY_MODEL_ID`) écrit 3 questions auxquelles la réponse
  répond, et on prend la similarité cosinus moyenne (Cohere Embed v4, les embeddings du pipeline) avec la question d'origine.
  Un refus ou une réponse évasive vaut 0. Elle ne regarde pas la référence : une réponse fausse
  mais centrée sur la question score haut ; c'est le verdict du juge qui dit si elle est juste.
  Coût : un appel Ministral 3 par réponse. `--no-answer-relevancy` la désactive.

Sur les réponses sauvegardées du run du 4 septembre (calcul a posteriori, même code) :

| | Faithfulness /5 | Answer relevancy | … sur les CORRECT | … sur les INCORRECT | … sur les refus |
|---|---|---|---|---|---|
| Baseline | 4,73 | 0,710 (26) | 0,840 (17) | 0,596 (7) | 0,0 (2) |
| Agentic | 4,79 | 0,805 (24) | 0,798 (20) | 0,842 (4) | — |

L'écart de relevancy entre les modes vient surtout des refus, qui valent 0 : l'agentic n'en a
pas. Les 4 hallucinations de l'agentic restent centrées sur la question (0,84) : elles se
trompent de chiffre, elles ne répondent pas à côté.

### Retrieval exact, grâce aux pages annotées

FinanceBench annote la **page** de chaque preuve (zero-indexed). L'ingestion conserve le numéro de
page en metadata sur chaque chunk, ce qui donne des métriques de retrieval sans matching flou :

- **`page_hit@k`** — au moins un des k premiers chunks vient-il d'une page de preuve ?
- **`page_recall@k`** — quelle proportion des pages de preuve distinctes est couverte ?

Une tolérance de ±1 page absorbe un éventuel décalage entre la pagination du PDF et celle de l'OCR.

S'y ajoutent, par mode :

- **`evidence_seen_rate`** — la preuve figure-t-elle parmi les documents effectivement transmis au
  LLM ? C'est la métrique qui borne l'accuracy : le modèle ne peut pas répondre juste à partir
  d'une preuve qu'il n'a pas vue. Pour le mode agentic, elle compte aussi les passages ramenés
  par les outils ; le delta avec baseline mesure donc l'apport réel de la boucle agentique.
- **`corrective_rate`** (agentic) — part des questions où le modèle a appelé au moins un outil.
- **`mean_tool_calls_when_corrected`** / **`pages_read_rate_when_corrected`** (agentic) — sur ces
  questions, nombre moyen d'appels d'outils, et part où au moins une page entière a été lue
  (`read_page`). Chaque ligne de résultat liste aussi `pages_read` et la trace des appels dans
  `corrective_queries`.
- `financebench_results.json` contient aussi, par question, les 20 `(document, page)` récupérés
  et `gold_rank` (rang de la première page de preuve), pour diagnostiquer le retrieval sans
  relancer d'appels API.

### Métriques de retrieval

`recall@k`, `precision@k`, `mrr@k`, `ndcg@k` (matching textuel sur les passages de preuve),
`context_hit_rate` et `mean_f1` viennent de `backend/evals/experiment_utils.py`. `page_precision@k` est la
part des k premiers passages qui viennent d'une page de preuve.

⚠️ **La précision est plafonnée par construction.** Une question n'a souvent qu'une ou deux pages
de preuve : même un retrieval parfait ne met pas 10 passages pertinents dans un top-10. Elle se
lit d'un run à l'autre (le contexte contient-il moins de bruit ?), pas en valeur absolue. Run du
4 septembre, recalculé depuis les pages sauvegardées : `page_precision@5` 14,6 %,
`@10` 13,1 %, `@20` 8,7 % (identique dans les deux modes : même retrieval initial).

⚠️ **`mean_f1` est peu informatif ici** : les réponses attendues sont en prose
(« Data Center », « Performance is not measured through operating margin »), le recouvrement de
tokens ne mesure donc pas la justesse. C'est bien l'`accuracy` du juge qui fait foi — comme dans
le protocole officiel.

Le résumé est ventilé par `question_type` et par `question_reasoning`, pour voir sur quel type de
raisonnement le système décroche.

## Sorties

**Uniquement dans LangSmith**, rien en local (le runner refuse de tourner sans `LANGSMITH_API_KEY`) :


- **Une expérience par mode** (baseline / agentic) sur le dataset « agentic-search · FinanceBench » : une ligne par
  question et par répétition (réponse, verdict et raison du juge, F1, faithfulness, recall@k…,
  erreur technique éventuelle en métadonnée `error`), comparables côte à côte dans l'onglet
  « Experiments » ; accuracy, coût et stabilité en métadonnées de l'expérience.
- **Le résumé du run** (run `run_financebench_eval` du projet `agentic-search`, tag `eval`) : métriques agrégées par
  mode, deltas, ventilations, et le bloc `cost` : tokens facturés par modèle (callback LangChain sur
  chaque appel, juge compris), unités de recherche Cohere (`billed_units` de chaque réponse
  Rerank), total en dollars et en euros à la grille publique du jour (`cost.py`).

Un tableau de synthèse est aussi affiché en fin de run.

## Coût d'un run

Le tableau de fin de run affiche le coût, calculé à partir des tokens réellement facturés et des
grilles publiques (`cost.py`, avec la date de relevé et le taux de change utilisés). Ce n'est pas une estimation : ce sont les `usage` renvoyés par chaque appel.

Runs du 12 octobre 2026, avec outils seul (`--mode agentic`), Claude Sonnet 4.6 sur Bedrock :

| Run | Claude Sonnet 4.6 | Haiku 4.5 | Cohere Rerank 3.5 | Total |
|---|---|---|---|---|
| Pilote, 65 questions (595 s) | 1 151 565 tokens en entrée, 58 351 en sortie : 4,33 $ | 0,09 $ | 95 recherches : 0,19 $ | **4,61 $** |
| Corpus complet, 139 questions (2 080 s) | 2 464 547 en entrée, 102 418 en sortie : 8,93 $ | 0,27 $ | 200 recherches : 0,40 $ | **9,60 $** |

Soit ≈ 0,07 $ par question, ≈ 18 000 tokens lus. Le juge Qwen3 235B et Ministral 3 14B (answer
relevancy) ne sont pas dans la grille de `cost.py` : listés « non chiffrés », quelques dizaines de
centimes par run. `--mode both` ajoute la baseline sans outils, ≈ 3 000 tokens par question (≈ +1 $ sur
le pilote).

Le quota quotidien de tokens de Claude Sonnet 4.6 sur Bedrock se compte sur le compte AWS : plusieurs
runs complets dans la journée l'épuisent (« ThrottlingException … Too many tokens per day »), et les
questions concernées sont listées en échec. Les relancer le lendemain avec `--ids`, ou demander une
hausse dans AWS Service Quotas.

Ne sont pas comptés les embeddings de requête pendant le run (quelques dizaines de tokens par
recherche, négligeables) et la préparation, payée une fois : les embeddings des chunks (le texte
markdown est gratuit) et l'OCR des documents de `FULL_OCR_DOCS` (4 $ les 1 000 pages).

## Garde-fous de régression

L'éval complète mesure le système ; elle ne dit pas *ce qui* a cassé et coûte trop pour tourner
à chaque changement. `regression.py` fournit deux contrôles ciblés, à lancer **à la main** avant
de merger un changement de prompt, de chunking, de retrieval ou de modèle. Ils ne tournent pas en
CI : ils appellent les vraies API. La CI, elle, fait tourner les tests pytest, tous hors ligne.

```bash
# Retrieval seul, question par question contre une baseline versionnée (quelques centimes)
uv run python backend/evals/financebench/regression.py retrieval

# ~10 questions sentinelles, de bout en bout avec le juge (~0,10 €)
uv run python backend/evals/financebench/regression.py sentinels
```

**`retrieval`** rejoue le retrieval des 26 questions et compare le rang de la page de preuve à
`regression/retrieval_baseline.json`. Il échoue si une question perd sa preuve du top-10 (ce
que le modèle voit sans outils) ou si `page_hit@10` baisse de plus de 5 points. La comparaison
est faite question par question, parce qu'une perte compensée par un gain laisse la moyenne
inchangée. Après un changement voulu qui améliore le retrieval :
`regression.py retrieval --update-baseline`.

**`sentinels`** rejoue en mode agentic les questions de `regression/sentinels.json`, réussies au
run du 4 septembre, et vérifie le verdict du juge **et** la trajectoire : la page de preuve
a-t-elle été montrée au modèle ? Chaque sentinelle dit ce qu'elle protège (calcul de ratio,
preuve hors du top-10 atteinte seulement par les outils, réponse directe…). Un échec est
toléré par défaut (`--max-failures 1`) : le modèle à température 0 n'est pas strictement
déterministe ; relancer la question en échec départage.

Codes de sortie : `0` passe, `1` régression, `2` **run invalide**. Quand Cohere échoue (quota,
clé), le reranker rend l'ordre du retriever hybride sans lever d'erreur : le retrieval baisse et
ressemblerait à une régression du code. Les deux garde-fous le détectent et refusent de conclure.

La baseline actuelle est reprise du run versionné du 4 septembre, dont les derniers appels
Rerank avaient atteint le plafond Cohere : elle est à régénérer par un run live dès que la clé
fonctionne.

## Notes d'implémentation

- **Chunking récursif, pas sémantique.** La stratégie sémantique
  (`SemanticParentChildChunkingStrategy`) embed les paragraphes par batchs de 16 en série : sur
  un 10-K de 260 pages, cela représente des centaines d'appels API séquentiels. La préparation
  utilise donc explicitement `ParentChildChunkingStrategy` (parents 1200 / children 400).
- **Un seul retrieval par question.** `AgentWorkflow.full_pipeline()` relance un retrieval
  complet ; le runner invoque directement le graphe compilé avec les documents déjà récupérés,
  ce qui divise la latence par ~2 sans changer le comportement mesuré.
- **Comparaison honnête.** Les deux modes partagent exactement le même retrieval et les mêmes
  10 documents de contexte initiaux (`workflow._research_step`). Le seul écart est la boucle agentique :
  le delta mesure donc son apport propre, pas une différence de contexte.
- **Index scopé au jeu de documents.** L'espace Qdrant est nommé d'après un hash de la liste
  de documents (`eval_tenant_for`), pour éviter qu'un run lancé avec `--docs` sur un sous-ensemble
  n'interroge un index contenant d'autres documents.

## Licence

FinanceBench est distribué par Patronus AI (CC-BY-NC-4.0). Les PDF ne sont pas redistribués dans
ce dépôt : `prepare.py` les télécharge depuis le dépôt public.
