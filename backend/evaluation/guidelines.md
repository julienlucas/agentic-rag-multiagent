# Guidelines d'annotation (Q/A + passages gold)

## Objectif
Construire un dataset reproductible pour mesurer retrieval + réponse.

## Format JSONL
Chaque ligne = un exemple :
- `id`
- `file_name` ou `file_path`
- `question`
- `expected_answer`
- `answer_keywords`
- `gold_passages`

## Règles d'annotation
- `question` : courte, précise, sans ambiguïté.
- `expected_answer` : phrase claire et factuelle, extraite du document.
- `answer_keywords` : 3-6 mots/expressions qui doivent apparaître dans une bonne réponse.
- `gold_passages` : 1-3 extraits exacts du document (copié/collé) qui supportent la réponse.

## Exemples
- `gold_passages` doit être un extrait tel qu'il apparaît dans le document.
- Pas d'inférences ou de reformulations dans `gold_passages`.
