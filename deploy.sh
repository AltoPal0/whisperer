#!/bin/bash
# deploy.sh — Déploiement de Whisperer sur GCP
# Usage : bash deploy.sh [config.conf]
# Exemples :
#   bash deploy.sh                      → utilise whisperer.conf
#   bash deploy.sh terrassistant.conf   → déploie une instance Terrassistant

set -e

CONF="${1:-whisperer.conf}"
if [ ! -f "$CONF" ]; then
  echo "Erreur : fichier de config '$CONF' introuvable."
  exit 1
fi
source "$CONF"

SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

echo "==> Déploiement : $SERVICE"
echo "==> Projet     : $PROJECT_ID"
echo "==> Config     : $CONF"
gcloud config set project "$PROJECT_ID"

# ── 1. Permissions IAM ────────────────────────────────────────────────────────
echo ""
echo "==> Permissions IAM..."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.developer" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" --quiet

echo "    Permissions OK"

# ── 2. Secrets ────────────────────────────────────────────────────────────────
echo ""
echo "==> Secrets..."

create_secret_if_missing() {
  local name=$1
  local prompt=$2
  if ! gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
    echo ""
    echo "    Secret '$name' manquant."
    read -rsp "    $prompt : " value
    echo
    printf '%s' "$value" | gcloud secrets create "$name" \
      --project="$PROJECT_ID" \
      --replication-policy=automatic \
      --data-file=- --quiet
    echo "    Secret '$name' créé."
  else
    echo "    Secret '$name' : OK"
  fi
}

create_secret_if_missing "$SECRET_OPENAI"      "OPENAI_API_KEY"
create_secret_if_missing "$SECRET_DB_PASS"     "DB_PASS (mot de passe Cloud SQL)"
create_secret_if_missing "$SECRET_ADMIN_TOKEN" "ADMIN_TOKEN (token admin)"

if ! gcloud secrets describe "$SECRET_SMTP_PASS" --project="$PROJECT_ID" &>/dev/null; then
  echo ""
  echo "    Secret '$SECRET_SMTP_PASS' manquant."
  read -rsp "    SMTP_PASS : " smtp_pass_value
  echo
  printf '%s' "$smtp_pass_value" | gcloud secrets create "$SECRET_SMTP_PASS" \
    --project="$PROJECT_ID" --replication-policy=automatic --data-file=- --quiet
  echo "    Secret '$SECRET_SMTP_PASS' créé."
else
  echo "    Secret '$SECRET_SMTP_PASS' : OK"
fi

# ── 3. Artifact Registry ──────────────────────────────────────────────────────
echo ""
echo "==> Activation Artifact Registry..."
gcloud services enable artifactregistry.googleapis.com --project="$PROJECT_ID" --quiet

if ! gcloud artifacts repositories describe cloud-run-source-deploy \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  gcloud artifacts repositories create cloud-run-source-deploy \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID" --quiet
  echo "    Repo Artifact Registry créé"
else
  echo "    Repo Artifact Registry déjà existant"
fi

# ── 4. Variables & secrets Cloud Run ─────────────────────────────────────────
ENV_VARS="CLOUD_SQL_CONNECTION_NAME=${SQL_CONNECTION},DB_USER=whisperer,DB_NAME=whisperer"
ENV_VARS="${ENV_VARS},SMTP_HOST=${SMTP_HOST},SMTP_PORT=${SMTP_PORT}"
ENV_VARS="${ENV_VARS},SMTP_USER=${SMTP_USER},SMTP_FROM=${SMTP_FROM},DIGEST_TO=${DIGEST_TO}"

SECRETS="${SECRET_OPENAI}=openai-api-key:latest"
SECRETS="${SECRETS},DB_PASS=${SECRET_DB_PASS}:latest"
SECRETS="${SECRETS},ADMIN_TOKEN=${SECRET_ADMIN_TOKEN}:latest"
SECRETS="${SECRETS},SMTP_PASS=${SECRET_SMTP_PASS}:latest"

# Reformater pour --set-secrets (KEY=secret-name:version)
SET_SECRETS="OPENAI_API_KEY=${SECRET_OPENAI}:latest,DB_PASS=${SECRET_DB_PASS}:latest,ADMIN_TOKEN=${SECRET_ADMIN_TOKEN}:latest,SMTP_PASS=${SECRET_SMTP_PASS}:latest"

# ── 5. Déploiement Cloud Run ──────────────────────────────────────────────────
echo ""
echo "==> Déploiement Cloud Run (build ~3-5 min)..."
cd "$(dirname "$0")"

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --project "$PROJECT_ID" \
  --set-secrets="$SET_SECRETS" \
  --set-env-vars="$ENV_VARS" \
  --add-cloudsql-instances="$SQL_CONNECTION" \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5

echo ""
echo "==> Déploiement terminé !"
URL=$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "==> URL : $URL"
echo "==> Admin panel : ${URL}/admin.html"

# ── 6. Cloud Scheduler ────────────────────────────────────────────────────────
echo ""
echo "==> Cloud Scheduler (digest 23h00)..."
gcloud services enable cloudscheduler.googleapis.com --project="$PROJECT_ID" --quiet

ADMIN_TOKEN_VALUE=$(gcloud secrets versions access latest \
  --secret="$SECRET_ADMIN_TOKEN" --project="$PROJECT_ID")
DIGEST_URL="${URL}/api/admin/send-digest?token=${ADMIN_TOKEN_VALUE}"

if gcloud scheduler jobs describe "$SCHEDULER_JOB" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" \
    --location="$REGION" --project="$PROJECT_ID" \
    --schedule="0 23 * * *" --uri="$DIGEST_URL" \
    --http-method=POST --time-zone="$TIMEZONE" --quiet
  echo "    Job Scheduler mis à jour (23h00 $TIMEZONE)"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --location="$REGION" --project="$PROJECT_ID" \
    --schedule="0 23 * * *" --uri="$DIGEST_URL" \
    --http-method=POST --time-zone="$TIMEZONE" --quiet
  echo "    Job Scheduler créé (23h00 $TIMEZONE)"
fi

echo ""
echo "==> Tout est opérationnel !"
echo "    URL     : $URL"
echo "    Admin   : ${URL}/admin.html"
echo "    Digest  : chaque soir à 23h00 ($TIMEZONE)"
