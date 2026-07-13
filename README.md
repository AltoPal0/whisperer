# Whisperer

Dictaphone mobile installable (PWA) : on ouvre l'URL d'un « canal », on
enregistre sa voix, la transcription (via l'API OpenAI Whisper) apparaît
automatiquement et reste consultable dans l'historique du canal. Pas de
compte utilisateur — l'URL du canal fait office de clé d'accès partagée.

Ce document explique comment installer et déployer Whisperer **from
scratch** sur un nouveau projet Google Cloud Platform (GCP), à toi seul
(aucune ressource GCP n'est partagée avec le projet d'origine).

## Fonctionnalités

- Enregistrement audio depuis le mobile, transcription automatique (OpenAI Whisper)
- Plusieurs « canaux » indépendants, chacun installable comme une app à part (icône, nom) sur l'écran d'accueil
- Panneau d'administration (protégé par un jeton) pour créer des canaux et consulter toutes les transcriptions
- Export quotidien des données par email (voir plus bas — solution ad hoc, pas obligatoire)

## Architecture

- **Frontend** : PWA statique (HTML/CSS/JS), servie directement par le backend — pas d'hébergement séparé
- **Backend** : FastAPI (Python), sur Cloud Run
- **Base de données** : PostgreSQL sur Cloud SQL (SQLite en local, bascule automatique)
- **Transcription** : API OpenAI Whisper
- **Export quotidien** : API Resend + Cloud Scheduler (voir `DEPLOY.md`, section « Pourquoi un envoi d'email quotidien » — ce choix est spécifique au déploiement d'origine, pas une contrainte à reconduire telle quelle)

## Prérequis

- Un compte Google Cloud avec un moyen de paiement configuré (facturation activable)
- Une clé API [OpenAI](https://platform.openai.com/api-keys) (pour Whisper)
- Un compte [Resend](https://resend.com) avec une clé API et un domaine expéditeur vérifié — uniquement si tu gardes le digest email tel quel
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installé sur ta machine

## Installation from scratch

### Étape 0 — Créer le projet GCP

```bash
gcloud auth login

# Choisis un ID unique (lettres minuscules, chiffres, tirets)
gcloud projects create TON_PROJECT_ID --name="Whisperer"

gcloud config set project TON_PROJECT_ID
```

Relie ensuite un compte de facturation au projet (nécessaire pour créer des
ressources) :
```bash
gcloud billing accounts list
gcloud billing projects link TON_PROJECT_ID --billing-account=TON_BILLING_ACCOUNT_ID
```

Active les APIs Google nécessaires :
```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com
```

### Étape 1 — Créer l'instance Cloud SQL

```bash
gcloud sql instances create whisperer-db \
  --database-version=POSTGRES_16 \
  --tier=db-g1-small \
  --region=europe-west1

gcloud sql databases create whisperer --instance=whisperer-db

gcloud sql users create whisperer \
  --instance=whisperer-db \
  --password="CHOISIS_UN_MOT_DE_PASSE"
```

Garde ce mot de passe, il servira à l'étape 3.

Le schéma des tables (`channels`, `transcriptions`) est créé automatiquement
au premier démarrage de l'application — rien à faire de plus ici.

### Étape 2 — Cloner le dépôt et configurer

```bash
git clone <URL_DU_DEPOT_PRIVE>
cd whisperer
cp whisperer.conf.example whisperer.conf
```

Éditer `whisperer.conf` (ce fichier est ignoré par git, il reste local) :

| Variable | Valeur |
|---|---|
| `PROJECT_ID` | l'ID choisi à l'étape 0 |
| `PROJECT_NUMBER` | `gcloud projects describe TON_PROJECT_ID --format="value(projectNumber)"` |
| `REGION` | `europe-west1` (garder la même région que Cloud SQL) |
| `SQL_INSTANCE` | `whisperer-db` (ou le nom choisi à l'étape 1) |
| `SMTP_FROM` | adresse expéditeur vérifiée sur Resend |
| `DIGEST_TO` | adresse qui recevra le digest quotidien |

### Étape 3 — Déployer

```bash
bash deploy.sh whisperer.conf
```

Le script va poser les permissions IAM nécessaires, créer les secrets
manquants dans Secret Manager (il te les demande en interactif : clé
OpenAI, mot de passe DB choisi à l'étape 1, un jeton admin à inventer, clé
Resend), builder l'image via Cloud Build et déployer sur Cloud Run, puis
programmer le digest quotidien dans Cloud Scheduler. Comptez 3 à 5 minutes.

À la fin, il affiche l'URL du service Cloud Run et celle du panneau admin
(`/admin.html`).

### Étape 4 — Créer un premier canal

```bash
curl -X POST "https://TON_URL_CLOUD_RUN/api/admin/channels?token=TON_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "monequipe", "name": "Mon équipe"}'
```

L'app est ensuite accessible et installable à `https://TON_URL_CLOUD_RUN/c/monequipe`.

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

- **`DEPLOY.md`** : redéploiements ultérieurs, détails sur le choix Resend pour l'export, alternative `push.sh`.
- **`CLAUDE.md`** : si tu utilises un agent IA (Claude Code ou autre) pour effectuer ce déploiement, ce fichier lui donne des garde-fous spécifiques à ce projet.
