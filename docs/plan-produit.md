# Plan produit : le RAG agentique en libre-service, payé au crédit

Rédigé le 12 octobre 2026. Point de départ : le dépôt au commit `4553da6` (FinanceBench à 88 %).

## 0. Ce qui existe déjà

| Brique | État actuel | Ce qui manque pour un produit |
|---|---|---|
| Backend | Django sans base de données (`DATABASES = {}`), API JSON dans `backend/endpoints.py` | Utilisateurs, documents, crédits, paiements |
| Multi-tenant Qdrant | Une collection partagée, `tenant_id` sur chaque point (index `is_tenant`, HNSW par tenant) | Le tenant est le `session_id` envoyé par le client : **aucune isolation réelle**. Il doit venir de l'authentification |
| Stockage des originaux | Disque local `DOCUMENT_STORAGE_DIR`, rangé par hash | Un volume Railway persistant, avec un accès lié au compte |
| Ingestion | Synchrone dans la requête HTTP | File en base, traitée en arrière-plan : l'OCR d'un 10-K prend plusieurs minutes |
| Formats | Liste blanche `.pdf .docx .txt .md` (`file_handler.py:101`, `examples.ts:77`) | Voir §3 : en pratique **seul le PDF fonctionne** |
| Frontend | SPA Vite + React 18 + Tailwind 4, une page démo (accent or) | Routeur, landing, tarifs, connexion, espace app |

## 1. Modèle économique : crédits et marge

### Coûts réels mesurés

| Poste | Coût | Source |
|---|---|---|
| Une question (Sonnet 4.6 + Haiku + rerank) | **≈ 0,07 $ ≈ 0,06 €** en moyenne, jusqu'à ≈ 0,15 $ pour une question longue | Expériences LangSmith du 12/10 : 9,60 $ / 139 questions |
| Une page indexée (Mistral OCR + Cohere Embed v4) | **≈ 0,0012 $ ≈ 0,001 €** (OCR ≈ 1 $ / 1 000 pages, embeddings négligeables) | Grilles publiques, à revérifier |
| Volume Railway + Qdrant par document | Négligeable à l'unité (volume ≈ 0,15 $/Go/mois) ; Qdrant Cloud est un coût fixe | |
| Stripe (cartes UE) | 1,5 % + 0,25 € par paiement, soit ≈ 4 % sur un pack de 10 € | |
| Fixe mensuel | Railway (API + volume) ≈ 20-40 €, Postgres ≈ 5-20 €, Qdrant Cloud ≈ 30-100 € | |

### Grille proposée : 1 crédit = 0,01 €

| Action | Prix en crédits | Prix client | Coût | Marge brute |
|---|---|---|---|---|
| Une question | 20 crédits | 0,20 € | ≈ 0,06 € | **≈ 70 %** |
| Une page indexée | 1 crédit | 0,01 € | ≈ 0,001 € | ≈ 90 % |
| Stockage, consultation, suppression | gratuit | | | |

**Marge recommandée : un coefficient ×3 à ×3,5 sur le coût variable, soit environ 70 % de marge brute.**
- En dessous de ×2,5, les questions longues (0,15 $) et le gratuit mangent la marge.
- Une fois retirés Stripe (≈ 3-4 %), le coût du gratuit et le fixe, il reste **environ 50-55 % de marge nette** à volume modeste. C'est la norme d'un SaaS d'IA (50-70 %). Le fixe est couvert dès ≈ 150-200 € de chiffre d'affaires par mois.
- Le modèle d'agentik (prix fournisseur sans marge, 5,5 % de frais de rechargement) convient à une passerelle. Ici, la valeur est le pipeline (88 % sur FinanceBench) : elle justifie une marge sur l'usage.
- Prix fixe par question, plutôt que facturé au token : c'est prévisible pour le client. En interne, chaque question enregistre son coût réel pour surveiller la marge, et les 20 crédits se réajustent si la moyenne dérive.

### Offres (page Tarifs)

| | Gratuit | À la carte | Équipe |
|---|---|---|---|
| Prix | 0 €, sans carte | Packs prépayés : 10 € → 1 000 cr., 25 € → 2 600 cr., 50 € → 5 400 cr., 100 € → 11 000 cr. | Sur devis |
| Documents | **20 documents**, 1 000 pages au total, indexation offerte | 500 documents, 20 000 pages | Sur mesure |
| Questions | 300 crédits offerts (15 questions) | Au crédit | Au crédit, facture mensuelle |
| Formats | Tous | Tous | Tous |

- Coût maximal d'un compte gratuit : ≈ 1 € d'OCR + ≈ 1 € de questions, soit **≈ 2 € par inscription**, souvent moins. Protections : e-mail vérifié, un compte par e-mail, limite de débit.
- Bonus des gros packs plafonné à 10 % : au pack de 100 €, une question revient à 0,18 € et la marge reste ≈ 65 %.
- Les crédits n'expirent pas. Le prix s'affiche avant chaque action (« Indexer ce document : 142 crédits »), comme chez agentik.
- À trancher : prix TTC (B2C, Stripe Tax) ou HT (B2B).

## 2. Architecture cible

```
Navigateur ── Vercel (SPA) ── rewrite /api/* ──> Railway : Django (API + ingestion en arrière-plan)
                                                   ├── Volume Railway /data (fichiers originaux)
                                                   ├── Postgres Railway (utilisateurs, documents, crédits)
                                                   ├── Qdrant Cloud (chunks + pages, filtrés par workspace)
                                                   └── Stripe (paiements, webhook)
```

- **Un seul domaine** : Vercel relaie `/api/*` vers Railway, donc les cookies de session restent de première partie (pas de CORS ni de cookie tiers).
- **Postgres** (Railway Postgres) avec l'ORM Django, `dj-database-url`.
- **Stockage des fichiers : un volume Railway** monté sur le service web (`DOCUMENT_STORAGE_DIR=/data/documents`), en région UE. Les fichiers ne vont pas dans Postgres. Ils sont rangés par hash de contenu (`<hash>.<ext>`, plus `<hash>.pdf` pour un format converti) et servis par l'API après contrôle de l'espace.
- **File de tâches en base, sans worker séparé** : un volume Railway ne s'attache qu'à un service, et l'ingestion doit lire les originaux. Le service web lance donc une boucle de fond qui dépile les documents `queued` (`SELECT … FOR UPDATE SKIP LOCKED`) et exécute OCR → chunks → embeddings → Qdrant. Elle reprend après un redémarrage les documents restés en cours. Volume à sauvegarder (snapshots Railway).

### Modèle de données

| Table | Champs principaux |
|---|---|
| `User` | Django auth, e-mail comme identifiant, e-mail vérifié |
| `Workspace` | id UUID (**= `tenant_id` Qdrant**), propriétaire, offre, quotas |
| `Membership` | user, workspace, rôle (pour l'offre Équipe, plus tard) |
| `Document` | workspace, `file_hash`, nom, type, taille, pages, nom du fichier stocké, statut (`en attente`, `OCR`, `indexation`, `prêt`, `erreur`), erreur, crédits facturés, dates |
| `CreditLedger` | Écritures en ajout seul : workspace, delta, motif (`bienvenue`, `achat`, `question`, `indexation`, `remboursement`), référence (paiement Stripe, document, run LangSmith), coût réel en $ |
| `Question` | workspace, user, question, réponse, citations, `run_id`, tokens, coût réel, crédits. Elle sert l'historique du chat et le suivi de la marge |
| `Purchase` | Session Stripe, pack, montant, statut |

Le solde est la somme du registre, lu avec `SELECT … FOR UPDATE` sur le workspace. Une question réserve ses 20 crédits avant de partir et les rembourse si elle échoue. Une indexation réserve `pages × 1` à l'envoi et les rend sur une page en erreur.

### Authentification

- **django-allauth en mode headless**, prévu pour une SPA : e-mail et mot de passe, vérification d'e-mail, mot de passe oublié, **connexion Google**. L'e-mail transactionnel passe par Resend ou Amazon SES.
- Session par cookie `HttpOnly` + CSRF, sans JWT à gérer côté client.
- Tous les endpoints `api/*` (sauf la démo publique) exigent une session. Le `session_id` disparaît de l'API.

### Multi-tenant Qdrant

- `tenant_id` = `Workspace.id`, tiré de la session côté serveur, jamais du client. `qdrant_store.py` garde son filtre obligatoire.
- Quotas (`TENANT_MAX_DOCUMENTS`, `TENANT_MAX_CHUNKS`) lus sur l'offre du workspace, et non plus dans l'environnement.
- Postgres fait foi pour la liste des documents ; Qdrant en est l'index. Supprimer un document enlève ses points, puis son fichier du volume quand plus aucun workspace ne l'indexe.
- On garde la copie de vecteurs entre tenants pour un fichier identique (même hash) : pas de second OCR, aucune fuite, puisque l'utilisateur détient le fichier. Un test vérifie qu'aucune requête ne lit hors du workspace.
- La démo publique (AMD, Boeing) vit dans un workspace « démo » en lecture seule. Les collections `eval_*` ne bougent pas.
- Migration : on purge les tenants `session_id` existants.

## 3. Formats de fichiers

**Aujourd'hui** : la liste blanche accepte `.pdf .docx .txt .md`, mais `_ocr()` envoie **tout** à Mistral OCR comme `data:application/pdf`. Un `.docx`, un `.txt` ou un `.md` échoue donc (OCR vide, document ignoré). **En pratique, seul le PDF fonctionne.** Un test le confirmera.

**Cible** : chaque format est ramené à des « pages » de markdown, le PageStore et les outils (`read_page`, `grep`, `navigate`) restent inchangés.

| Formats | Traitement | Citation ouverte dans |
|---|---|---|
| PDF | Mistral OCR (inchangé) | pdf.js, à la page |
| DOCX, PPTX, ODT, RTF | Conversion en PDF par LibreOffice sans interface (dans l'image Docker), puis OCR | pdf.js, à la page |
| PNG, JPG, WEBP, TIFF | Mistral OCR en `image_url` : une image = une page | L'image |
| TXT, MD, HTML | Lus directement (HTML → markdown), découpés en pages d'environ 3 000 caractères, sans OCR (indexation quasi gratuite) | Panneau texte, passage surligné |
| XLSX, CSV | Un tableau markdown par feuille, une page par tranche de 50 lignes | Panneau texte |

Limites : 50 Mo et 500 pages par fichier. Le type se détecte par le contenu (magic bytes), pas par l'extension.

## 4. Interface (inspirée d'agentik.cc)

**Langage visuel relevé sur agentik.cc** : fond blanc, police **Geist** et **Geist Mono** pour les chiffres, prix et étiquettes. Encre `#101522`, texte secondaire `#586379`, filets `#e6ebf4`. Notre charte reste (papier, encre `#101522`, filets), avec un **accent orange** à la place de l'or. Largeur maximale 1 200 px, rayon 10 px. Sections numérotées `01 … 06` en mono, puces de prix (« FLUX.2 · 0,03 $ »), tableaux comparatifs sobres, transitions courtes (150-250 ms). Base shadcn/neutral : elle correspond aux composants `ui/` déjà présents.

Routeur : `react-router` 7.

| Route | Contenu |
|---|---|
| `/` | Hero (« Interrogez vos documents. Chaque réponse citée, page à l'appui. »), CTA « Commencer gratuitement, 20 documents ». Bande de puces de prix (« Question · 20 cr. », « Page indexée · 1 cr. »). Sections numérotées : 01 Déposez, 02 L'agent cherche (les 5 outils), 03 Citations ouvertes dans le document, 04 Mesuré (88 % FinanceBench), 05 Prix, 06 Sécurité (espace isolé, données en UE). La démo publique AMD/Boeing reste jouable sans compte |
| `/tarifs` | Cartes Gratuit / À la carte / Équipe, tableau « Ce qui est inclus », **calculateur** (10 / 25 / 50 / 100 € → crédits, nombre de questions, nombre de pages), « Ce que quelques euros achètent », FAQ |
| `/connexion`, `/inscription` | E-mail + mot de passe, bouton Google, lien mot de passe oublié. Écran « vérifiez votre e-mail » |
| `/app` | Mise en page avec barre latérale (Chat, Documents, Crédits, Compte) et solde de crédits toujours visible |
| `/app/documents` | Zone de dépôt (glisser-déposer, plusieurs fichiers, coût estimé avant envoi), tableau (nom, type, pages, statut en direct, date, crédits ; ouvrir, supprimer), quota « 12 / 20 documents » |
| `/app/chat` | `DemoChat` + `DocumentViewer` réutilisés, choix des documents interrogés, historique des conversations, coût affiché par réponse |
| `/app/credits` | Solde, achat de packs (Stripe Checkout), relevé de chaque opération avec son coût (comme les reçus d'agentik) |
| `/app/compte` | Profil, mot de passe, suppression du compte (efface Postgres, le volume et Qdrant) |

## 5. Étapes

**État au 12 octobre 2026** : étapes 1 à 5 faites et testées (272 tests, parcours complet vérifié dans Chrome contre les vrais services). Reste l'étape 6 : configurer Railway, Vercel, Stripe, l'e-mail et Google.


1. **Fondations backend** : Postgres, modèles, migrations, allauth headless, endpoints protégés, workspace créé à l'inscription avec 300 crédits.
2. **Multi-tenant et stockage** : `tenant_id` issu de la session, volume Railway, Document en base, ingestion en arrière-plan avec statuts. Tests d'isolation.
3. **Formats** : détection du type, LibreOffice, images, texte, tableurs. Tests par format.
4. **Crédits et paiement** : registre, réservation et remboursement, Stripe Checkout + webhook, quotas par offre, coût réel enregistré.
5. **Frontend** : thème (notre charte, accent orange), routeur, landing, tarifs, connexion et inscription, espace app (documents, chat, crédits, compte).
6. **Mise en production** : variables Railway et Vercel, rewrite `/api`, limites de débit, CGU et confidentialité (RGPD, données en UE), éval FinanceBench de non-régression après la migration.

## 6. Décisions et questions ouvertes

- ✅ Accent : **orange**, le reste de notre charte (papier, encre, filets, Geist) est conservé.
- ✅ Stockage : **volume Railway**, pas de S3.
- Nom du produit et domaine (provisoire : Agentic Search).
- Prix TTC (grand public) ou HT (professionnels) ?
- Compte Stripe existant ?
- Garder l'historique des conversations dès la V1 (proposé : oui) ?
