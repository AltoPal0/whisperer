# Whisperer — guide pour agent IA (déploiement sur un nouveau compte GCP)

Ce projet a été développé et déployé par quelqu'un d'autre sur son propre
compte Google Cloud. Si tu es un agent IA chargé de le redéployer, tu pars
d'un environnement **vierge** : aucun projet GCP, aucun outil, aucun secret
ne peut être supposé présent. Ne réutilise aucune valeur d'exemple (project
ID, URL, noms de secrets) trouvée dans l'historique git ou les commentaires —
elle appartient à l'ancien déploiement.

Le guide de référence pour les étapes de déploiement est **`DEPLOY.md`**.
Ce fichier-ci ne le duplique pas : il donne les précautions à prendre en tant
qu'agent avant de l'exécuter.

## Avant toute chose : vérifier ce qui est réellement disponible

Ne suppose rien sur la machine de l'utilisateur. Vérifie explicitement, et
propose l'installation si absent (n'installe pas sans confirmation) :

```bash
gcloud --version          # gcloud CLI — obligatoire (déploiement via Cloud Build)
gcloud auth list          # un compte doit être authentifié
gcloud config get-value project   # peut être vide ou pointer sur un autre projet
docker --version          # optionnel — seulement requis si push.sh est utilisé à la place de deploy.sh
```

`deploy.sh` déploie via `gcloud run deploy --source .` (Cloud Build distant) :
**Docker n'est pas nécessaire** sur la machine locale pour le chemin
principal. Ne présuppose pas non plus la présence de `python`/`pip` en local
sauf si l'utilisateur veut lancer le backend en dev.

## Ne jamais deviner les identifiants

Certaines valeurs doivent venir de l'utilisateur, jamais être inventées ou
réutilisées d'un exemple :
- ID / numéro du projet GCP cible (demander ou le faire créer explicitement)
- Clé API OpenAI
- Clé API Resend + adresse expéditeur vérifiée
- Adresse destinataire du digest (`DIGEST_TO`)
- Mot de passe de la base Cloud SQL (proposer d'en générer un fort, mais avec confirmation)

`ADMIN_TOKEN` est la seule valeur que tu peux générer toi-même (ex.
`openssl rand -hex 32`) sans demander, car c'est un jeton interne à
l'application, pas un identifiant tiers.

## Précautions spécifiques à ce projet

- **`whisperer.conf` n'existe pas dans un checkout frais** (il est
  `.gitignore`d) — il faut le créer à partir de `whisperer.conf.example` avec
  les valeurs du nouveau projet, jamais réutiliser un fichier `.conf` déjà
  présent sans vérifier son contenu.
- `deploy.sh` **ne crée pas l'instance Cloud SQL** — vérifier qu'elle existe
  avant de lancer le script (voir Étape 1 de `DEPLOY.md`), sinon le déploiement
  Cloud Run réussira mais l'app ne pourra pas se connecter à la base.
- Avant de créer une ressource (instance Cloud SQL, secret, repo Artifact
  Registry...), vérifier qu'elle n'existe pas déjà (`gcloud ... describe`) —
  `deploy.sh` le fait déjà pour les secrets et le repo, mais pas pour Cloud SQL.
- Le projet GCP cible doit avoir la facturation activée avant toute commande
  `gcloud` de création de ressource — sinon les erreurs sont peu explicites.
- Ne jamais committer de fichier `*.conf` rempli ni aucune valeur de Secret
  Manager dans git.
- Le digest email est un mécanisme d'**export de données** (voir DEPLOY.md,
  section « Pourquoi un envoi d'email quotidien ») — ne pas le désactiver ou
  le simplifier sans vérifier avec l'utilisateur, ce n'est pas une feature
  annexe.
- **Resend n'est pas l'architecture cible, juste le choix fait pour le
  déploiement personnel d'origine.** Avant de reconduire tel quel le pipeline
  email (Cloud Scheduler → Resend), demande à l'utilisateur quel mécanisme
  d'export a du sens dans *son* environnement (bucket GCS, base partagée,
  endpoint interne...). Ne suppose pas que Resend doit être conservé juste
  parce que c'est ce que fait le code actuel — c'est un point de conception
  ouvert, pas un détail d'implémentation à copier.

## Ordre de travail recommandé

1. Lire `DEPLOY.md` en entier.
2. Vérifier les outils disponibles (section ci-dessus) et signaler ce qui manque.
3. Demander à l'utilisateur les valeurs qui ne peuvent pas être devinées (voir plus haut), **et** lui demander explicitement s'il veut garder le digest par email (Resend) ou le remplacer par un export direct adapté à son environnement.
4. Suivre `DEPLOY.md` étape par étape, en confirmant avant chaque action qui crée de la facturation (instance Cloud SQL, Cloud Run) ou qui touche un compte GCP réel.
