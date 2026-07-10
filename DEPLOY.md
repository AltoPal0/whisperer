# Déploiement de Whisperer sur GCP

Guide pour déployer cette application sur un projet Google Cloud Platform (GCP)
qui t'appartient. Le dépôt ne contient aucun secret ni identifiant de projet —
tout se configure via un fichier `*.conf` local (ignoré par git).

## Architecture

- **Frontend** : PWA statique (HTML/CSS/JS), servie directement par le backend
- **Backend** : FastAPI (Python 3.11) sur Cloud Run
- **Base de données** : PostgreSQL sur Cloud SQL
- **Transcription** : API OpenAI Whisper (nécessite une clé API OpenAI)
- **Email (digest quotidien)** : API Resend + Cloud Scheduler

## Pourquoi un envoi d'email quotidien

L'app n'a pas d'interface d'export : le digest email est le mécanisme par
lequel les données transcrites sortent de Whisperer (copie/sauvegarde vers une
boîte mail plutôt que consultation via l'admin panel). Chaque soir, Cloud
Scheduler déclenche un envoi qui regroupe les transcriptions du jour par canal
et les attache en JSON à un email.

L'envoi passe par l'API transactionnelle **Resend** plutôt que par un compte
SMTP classique (`smtplib`) précisément pour fiabiliser/simplifier cette copie
de données : pas de gestion de connexion SMTP/serveur, juste un appel HTTP
avec une clé API — plus robuste pour un envoi automatisé sans surveillance.

## Prérequis

1. Un projet GCP avec la facturation activée.
2. [gcloud CLI](https://cloud.google.com/sdk/docs/install) installé et authentifié :
   ```bash
   gcloud auth login
   gcloud config set project TON_PROJECT_ID
   ```
3. Une clé API OpenAI (pour Whisper).
4. Un compte [Resend](https://resend.com) avec une clé API et un domaine expéditeur vérifié (pour `SMTP_FROM`).

`deploy.sh` active lui-même les APIs nécessaires (Artifact Registry, Cloud
Scheduler) et pose les permissions IAM, mais il **ne crée pas l'instance
Cloud SQL** — c'est la seule étape manuelle avant le premier déploiement.

## Étape 1 — Créer l'instance Cloud SQL

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

Garde ce mot de passe : il sera stocké dans Secret Manager à l'étape 3
(le secret s'appelle `db-password`).

## Étape 2 — Appliquer le schéma

Le schéma de base est créé automatiquement au démarrage de l'app (SQLAlchemy
`create_all` dans `backend/db.py`). La migration `migrate.sql` ne s'applique
que si tu reprends une base Whisperer existante — pour un premier déploiement
tu peux l'ignorer.

Si besoin de l'exécuter manuellement :
```bash
gcloud sql connect whisperer-db --user=whisperer --database=whisperer < migrate.sql
```

## Étape 3 — Configurer le déploiement

```bash
cp whisperer.conf.example whisperer.conf
```

Éditer `whisperer.conf` et renseigner :
- `PROJECT_ID` : l'ID exact de ton projet GCP (`gcloud projects describe TON_PROJECT_ID`)
- `PROJECT_NUMBER` : `gcloud projects describe TON_PROJECT_ID --format="value(projectNumber)"`
- `REGION` : région GCP (`europe-west1` par défaut — garder la même région que Cloud SQL)
- `SQL_INSTANCE` : nom de l'instance créée à l'étape 1
- `SMTP_FROM` (adresse expéditeur vérifiée sur Resend) / `DIGEST_TO` (destinataire du digest)

`whisperer.conf` est ignoré par git — chaque développeur/environnement a le
sien.

## Étape 4 — Lancer le déploiement

```bash
bash deploy.sh whisperer.conf
```

Ce script va, dans l'ordre :
1. Poser les permissions IAM nécessaires (Cloud Build, Cloud Run, Cloud SQL, Secret Manager)
2. Créer les secrets manquants dans Secret Manager en te les demandant en interactif :
   `OPENAI_API_KEY`, `DB_PASS` (le mot de passe choisi à l'étape 1), `ADMIN_TOKEN` (à inventer), `RESEND_API_KEY`
3. Créer le repo Artifact Registry si absent
4. Builder et déployer l'image sur Cloud Run (branché à Cloud SQL via le connecteur natif)
5. Créer/mettre à jour un job Cloud Scheduler qui déclenche le digest quotidien à 23h (heure définie par `TIMEZONE`)

À la fin, le script affiche l'URL du service Cloud Run et de la page admin
(`/admin.html`).

## Redéploiements ultérieurs

- `bash deploy.sh whisperer.conf` relance un build+deploy complet (source → Cloud Build → Cloud Run) et remet à jour le job Scheduler.
- `push.sh` est une alternative qui build l'image Docker en local (utile si Cloud Build est indisponible ou pour tester l'image avant push) — il a des valeurs de projet en dur à adapter avant usage.

## Notes

- Le dev local n'a pas besoin de Cloud SQL : `backend/db.py` bascule sur SQLite (`sqlite+aiosqlite`) si `CLOUD_SQL_CONNECTION_NAME` n'est pas défini. Utiliser `backend/requirements.txt` (sans `asyncpg`, qui ne compile pas sur les Python très récents) pour le dev local, et `requirements-prod.txt` uniquement pour l'image Docker.
- `setup-gmail.sh` configure une intégration Gmail annexe, non requise pour le fonctionnement de base — à ignorer sauf besoin spécifique.
