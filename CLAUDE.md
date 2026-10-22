# Whisperer — guide pour agent IA

> **⚠️ Tout se gère depuis `../SG2`, pas depuis ce dépôt.** Whisperer tourne sur la plateforme SG2
> (projet GCP `sg2-platform`, compte `giloppe@gmail.com`, région `europe-west9`,
> https://whisperer.sg-square.com). Pour redéployer : `cd ../SG2 && bash apps/whisperer.sh`.
> L'infra (base `sg2-db`, secrets, Cloud Scheduler, sous-domaine Cloudflare) est décrite dans
> `../SG2/CLAUDE.md`. Ce dépôt ne contient plus de script de déploiement : n'en recrée pas ici.

## Précautions spécifiques à ce projet

- **Base partagée** : la base `whisperer` vit dans l'instance Cloud SQL `sg2-db` (db-f1-micro,
  25 connexions max) partagée avec d'autres apps. Le pool SQLAlchemy est réduit à 2 + 2
  (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW` dans `backend/db.py`) — ne pas l'augmenter, ni
  `--max-instances` (3), sans vérifier la marge.
- Ne jamais committer de secret ni de valeur de Secret Manager dans git.
- Le digest email est un mécanisme d'**export de données** (voir `DEPLOY.md`, section
  « Pourquoi un envoi d'email quotidien ») — ne pas le désactiver ou le simplifier sans
  vérifier avec l'utilisateur, ce n'est pas une feature annexe.
- **Resend n'est pas l'architecture cible**, juste le choix fait à l'origine. Avant de toucher au
  pipeline d'export (Cloud Scheduler → Resend), demander à l'utilisateur quel mécanisme a du sens.
- Le jeton admin passe en query string (`?token=…`) et apparaît donc dans les logs Cloud Run :
  amélioration connue, à traiter avec l'utilisateur.
- Dev local : sans `CLOUD_SQL_CONNECTION_NAME`, l'app bascule sur SQLite ; utiliser
  `backend/requirements.txt` (sans `asyncpg`) en local et `requirements-prod.txt` pour l'image Docker.
