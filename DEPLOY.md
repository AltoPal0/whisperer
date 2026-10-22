# Déploiement de Whisperer sur GCP

> **⚠️ Le déploiement se gère depuis `../SG2`, pas depuis ce dépôt** :
> `cd ../SG2 && bash apps/whisperer.sh`. Infra, secrets et sous-domaine : `../SG2/CLAUDE.md`.
> Les anciens `deploy.sh`, `push.sh`, `setup-gmail.sh` et fichiers `*.conf` ont été supprimés le 22/10/2026
> (ils restent dans l'historique git).

Ce document garde les choix de conception utiles pour comprendre le déploiement.

## Architecture

- **Frontend** : PWA statique (HTML/CSS/JS), servie directement par le backend
- **Backend** : FastAPI (Python 3.11) sur Cloud Run
- **Base de données** : PostgreSQL sur Cloud SQL (instance partagée `sg2-db`, base `whisperer`)
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

**⚠️ Resend est une solution ad hoc, pas l'architecture cible.** Elle a été
choisie pour le déploiement personnel d'origine, où il n'y avait ni
infrastructure de stockage/synchro existante ni équipe à qui déléguer autre
chose qu'un email. Dans un environnement de déploiement différent (infra
d'entreprise, accès réseau interne, stockage partagé déjà en place...), le
digest email par Resend n'est probablement **pas** la bonne solution
d'export — une copie directe des données (export vers un bucket GCS, une
base partagée, un endpoint interne, etc.) sera presque toujours plus simple
et plus fiable qu'un aller-retour par email. Ne pas reconduire Resend par
défaut : évaluer d'abord si l'environnement cible permet un export plus
direct.

## Notes

- Le dev local n'a pas besoin de Cloud SQL : `backend/db.py` bascule sur SQLite (`sqlite+aiosqlite`) si `CLOUD_SQL_CONNECTION_NAME` n'est pas défini. Utiliser `backend/requirements.txt` (sans `asyncpg`, qui ne compile pas sur les Python très récents) pour le dev local, et `requirements-prod.txt` uniquement pour l'image Docker.
- Le schéma est créé automatiquement au démarrage (SQLAlchemy `create_all` dans `backend/db.py`).
  `migrate.sql` ne sert que pour reprendre une ancienne base Whisperer.
