# API du produit (contrat backend ↔ frontend)

Toutes les routes sont servies sous le même domaine que le frontend (Vercel relaie `/api/*` et `/_allauth/*`
vers Railway ; en dev, le proxy Vite fait de même). Authentification par **cookie de session** Django.
Toute requête qui modifie quelque chose (POST, DELETE) envoie l'en-tête `X-CSRFToken` = valeur du cookie
`csrftoken` (posé par `GET /api/me`). Les réponses d'erreur ont la forme `{"error": "message lisible"}`.
Codes : 401 non connecté, 402 crédits insuffisants, 403 quota atteint, 404, 400.

## Authentification : django-allauth en mode headless, client « browser »

Préfixe `/_allauth/browser/v1`. Corps JSON. Réponses allauth (`{status, data, meta}`).

| Action | Requête |
|---|---|
| Inscription | `POST /auth/signup` `{email, password}` → 401 avec `data.flows[]` contenant `{id:"verify_email", is_pending:true}` : un code à 6 caractères est envoyé par e-mail |
| Vérifier l'e-mail (code) | `POST /auth/email/verify` `{key: "<code>"}` → 200, connecté |
| Connexion | `POST /auth/login` `{email, password}` → 200 connecté ; 401 + flow `verify_email` en attente si e-mail non vérifié ; 400 identifiants faux (`errors[].message`) |
| Session courante | `GET /auth/session` → 200 connecté, 401 sinon |
| Déconnexion | `DELETE /auth/session` |
| Mot de passe oublié | `POST /auth/password/request` `{email}` (code par e-mail) puis `POST /auth/password/reset` `{key, password}` |
| Google | formulaire HTML `POST /auth/provider/redirect` (champs `provider=google`, `callback_url=/app`, `process=login`, `csrfmiddlewaretoken`) — redirection navigateur |

## Public

| Route | Réponse |
|---|---|
| `GET /api/pricing` | `{credit_value_eur: 0.01, question_credits: 20, page_credits: 1, free: {documents: 20, pages: 1000, welcome_credits: 300}, paid: {documents: 500, pages: 20000}, packs: [{id:"pack_10", price_eur:10, credits:1000}, {id:"pack_25", price_eur:25, credits:2600}, {id:"pack_50", price_eur:50, credits:5400}, {id:"pack_100", price_eur:100, credits:11000}], formats: [".pdf", ".docx", …]}` |
| `GET /api/me` | Connecté : `{user: {email}, workspace: {id, plan: "free"|"paid", balance, documents_count, pages_count, max_documents, max_pages}}`. Sinon 401. Pose toujours le cookie `csrftoken`. |
| Démo publique (inchangée, `session_id`) | `POST /api/load-file`, `POST /api/process-question`, `GET /api/documents/page`, `GET /api/documents/<hash>/file`, `POST /api/feedback`. `POST /api/upload-file` est **supprimé** : déposer ses fichiers demande un compte. |

## Espace connecté (`/api/app/…`, 401 sans session)

### Documents
`Document` = `{id, name, kind: "pdf"|"docx"|…, size, pages, status: "queued"|"processing"|"ready"|"error", error, credits, created_at, file_url}`
(`file_url` : l'original à ouvrir dans le visualiseur, ou `null` si non affichable en PDF)

| Route | Réponse |
|---|---|
| `GET /api/app/documents` | `{documents: Document[]}` (plus récents d'abord) |
| `POST /api/app/documents` | multipart, un ou plusieurs champs `files`. Crée les documents en `queued`, réserve `pages × page_credits` (pages comptées à la réception). → `{documents: Document[], balance}`. 402 si solde insuffisant (rien n'est créé), 403 si quota dépassé, 400 si format non pris en charge. Une page déjà facturée ne l'est pas deux fois (même fichier déjà dans l'espace → renvoyé tel quel). |
| `DELETE /api/app/documents/<id>` | `{ok: true}` |
| `GET /api/app/documents/<id>/file` | l'original (PDF, ou PDF converti), `Content-Disposition: inline` |
| `GET /api/app/documents/page?document=<id>&page=<n>` | `{page, text}` (texte de la page, repli du visualiseur) |

Le frontend interroge `GET /api/app/documents` toutes les 3 s tant qu'un document est `queued` ou `processing`.

### Chat
| Route | Réponse |
|---|---|
| `POST /api/app/ask` `{question, conversation_id?}` | `{conversation_id, message: Message, balance}` ; interroge tous les documents `ready` de l'espace. 402 si solde < question_credits, 400 si aucun document prêt. |
| `GET /api/app/conversations` | `{conversations: [{id, title, updated_at}]}` |
| `GET /api/app/conversations/<id>` | `{id, title, messages: Message[]}` |
| `DELETE /api/app/conversations/<id>` | `{ok: true}` |

`Message` = `{id, question, answer, verification_report, citations: Citation[], credits, created_at, feedback_token}` où
`Citation` = celle de la démo (`{n, source, page, locator, excerpt, file_hash, pdf_url, text}`) ; pour l'espace connecté,
`pdf_url` vaut `/api/app/documents/<id>/file` (déjà complet, sans `session_id`).

| `POST /api/app/feedback` `{feedback_token, score: 0|1, comment?}` | `{message}` |

### Crédits
| Route | Réponse |
|---|---|
| `GET /api/app/credits` | `{balance, entries: [{id, delta, reason: "welcome"|"purchase"|"question"|"indexing"|"refund", label, created_at}]}` (100 dernières) |
| `POST /api/app/checkout` `{pack: "pack_25"}` | `{url}` (Stripe Checkout, retour sur `/app/credits?paid=1`) ; 503 si Stripe n'est pas configuré |

### Compte
| `DELETE /api/app/account` | supprime le compte, ses documents (Postgres, stockage, Qdrant) → `{ok: true}` |
