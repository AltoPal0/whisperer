# Whisperer

Dictaphone mobile installable (PWA) : on ouvre l'URL d'un « canal », on
enregistre sa voix, la transcription (via l'API OpenAI Whisper) apparaît
automatiquement et reste consultable dans l'historique du canal. Pas de
compte utilisateur — l'URL du canal fait office de clé d'accès partagée.

> **⚠️ Le déploiement se gère depuis `../SG2`, pas depuis ce dépôt.** Whisperer tourne sur la
> plateforme SG2 (projet GCP `sg2-platform`, https://whisperer.sg-square.com). Ce repo ne contient
> plus de script de déploiement — voir la section « Déploiement » plus bas.

## Fonctionnalités

- Enregistrement audio depuis le mobile, transcription automatique (OpenAI Whisper)
- Plusieurs « canaux » indépendants, chacun installable comme une app à part (icône, nom) sur l'écran d'accueil
- Panneau d'administration (protégé par un jeton) pour créer des canaux et consulter toutes les transcriptions
- Export quotidien des données par email (voir plus bas — solution ad hoc, pas obligatoire)

## Architecture

- **Frontend** : PWA statique (HTML/CSS/JS), servie directement par le backend — pas d'hébergement séparé
- **Backend** : FastAPI (Python), sur Cloud Run (`europe-west9`, projet `sg2-platform`)
- **Base de données** : PostgreSQL — base `whisperer` de l'instance Cloud SQL partagée `sg2-db` (SQLite en local, bascule automatique)
- **Transcription** : API OpenAI Whisper
- **Export quotidien** : API Resend + Cloud Scheduler (voir `DEPLOY.md`, section « Pourquoi un envoi d'email quotidien » — ce choix est spécifique au déploiement d'origine, pas une contrainte à reconduire telle quelle)

## Modèle de données & flux applicatif

Deux tables (`backend/db.py`, SQLAlchemy async, PostgreSQL/Cloud SQL en prod, SQLite en local via `DATABASE_URL`) :
- `channels(code PK, name, created_at)` — un canal = un espace de dictée isolé, identifié uniquement par son `code` (l'URL `/c/{code}` fait office de clé d'accès, pas d'auth utilisateur).
- `transcriptions(id, text, language, duration_ms, channel_code, created_at)`, indexée sur `(channel_code, created_at)`.

Routes (`backend/main.py`) :
- `GET /c/{code}` et `GET /manifest/c/{code}` — sert la PWA statique (`frontend/`) et son manifest, scopés au canal (icône/nom d'app par canal).
- `GET /api/channel/{code}` — infos du canal.
- `POST /api/transcribe` — reçoit l'audio enregistré côté client, l'envoie à l'API OpenAI Whisper (`backend/whisper_client.py`), stocke le texte résultant dans `transcriptions`.
- `GET /api/transcriptions` — historique d'un canal (consultation par l'utilisateur du canal, pas admin).
- `DELETE /api/transcriptions/{id}`.
- `POST /api/admin/channels`, `GET /api/admin/channels`, `GET /api/admin/transcriptions` — panneau admin, protégé par `ADMIN_TOKEN` (`_check_admin`), pas de rôle/utilisateur : un seul jeton partagé.
- `POST /api/admin/send-digest` — déclenche manuellement l'envoi du digest email (voir plus bas) ; c'est aussi cette route que Cloud Scheduler appelle chaque soir.

Le digest quotidien (`backend/mailer.py`) regroupe les transcriptions du jour par canal et les envoie par email via l'API Resend (pas de SMTP classique) — voir `DEPLOY.md` pour le détail et les réserves sur ce choix (solution ad hoc, pas l'architecture cible).

## Déploiement

Tout se pilote depuis le dossier `../SG2` (infra, secrets, sous-domaine : voir `../SG2/CLAUDE.md`) :

```bash
cd ../SG2 && bash apps/whisperer.sh
```

- Service Cloud Run `whisperer` (`europe-west9`) — https://whisperer.sg-square.com, admin sur `/admin.html`.
- Base `whisperer` dans l'instance partagée `sg2-db` (db-f1-micro, 25 connexions max) : le pool
  SQLAlchemy est réduit à 2 + 2 par défaut (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`), ne pas l'augmenter
  sans vérifier la marge de l'instance.
- Digest quotidien : job Cloud Scheduler `whisperer-daily-digest` (23h, Europe/Paris) dans `sg2-platform`.

Créer un canal :

```bash
curl -X POST "https://whisperer.sg-square.com/api/admin/channels?token=ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "monequipe", "name": "Mon équipe"}'
```

Le jeton est dans le secret `admin-token` de `sg2-platform`.

## Développement local

Pas besoin de Cloud SQL en local : sans `CLOUD_SQL_CONNECTION_NAME`,
l'application bascule automatiquement sur SQLite.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # sans asyncpg — utiliser requirements-prod.txt uniquement pour l'image Docker
cp .env.example .env              # renseigner au moins OPENAI_API_KEY et ADMIN_TOKEN
uvicorn main:app --reload
```

L'app est alors sur `http://localhost:8000`.

## Pour aller plus loin

- **`DEPLOY.md`** : détails sur le choix Resend pour l'export et notes techniques.
- **`CLAUDE.md`** : garde-fous pour un agent IA qui travaille sur ce dépôt.
