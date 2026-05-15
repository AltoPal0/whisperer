#!/bin/bash
# setup-gmail.sh — Setup complet sur giloppe@gmail.com
set -e

ACCOUNT="giloppe@gmail.com"
PROJECT_ID="whisperer-perso"
BILLING="01211B-B041E9-BE73B9"
REGION="europe-west1"
SERVICE="whisperer"
SQL_INSTANCE="whisperer-db"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE}:latest"

gcloud config set account "$ACCOUNT"
echo "==> Compte : $ACCOUNT"

# ── 1. Projet ─────────────────────────────────────────────────────────────────
echo ""
echo "==> Création du projet $PROJECT_ID..."
gcloud projects create "$PROJECT_ID" --name="Whisperer" 2>&1 || echo "    (projet déjà existant)"
gcloud config set project "$PROJECT_ID"

echo "==> Liaison facturation SG2..."
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING" --quiet

# ── 2. APIs ───────────────────────────────────────────────────────────────────
echo ""
echo "==> Activation des APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --project="$PROJECT_ID" --quiet

# ── 3. Cloud SQL ──────────────────────────────────────────────────────────────
echo ""
echo "==> Création Cloud SQL (~5 min)..."
gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_16 \
  --tier=db-g1-small \
  --edition=ENTERPRISE \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --no-backup 2>&1 || echo "    (instance déjà existante)"

echo "==> Base de données + utilisateur..."
gcloud sql databases create whisperer --instance="$SQL_INSTANCE" --project="$PROJECT_ID" 2>&1 || true

DB_PASS=$(grep MDP_USER_WHISPERER_SQL "$(dirname "$0")/backend/.env" | cut -d= -f2-)
gcloud sql users create whisperer \
  --instance="$SQL_INSTANCE" \
  --password="$DB_PASS" \
  --project="$PROJECT_ID" 2>&1 || true

# ── 4. Secrets ────────────────────────────────────────────────────────────────
echo ""
echo "==> Création des secrets..."
OPENAI_KEY=$(grep OPENAI_API_KEY "$(dirname "$0")/backend/.env" | cut -d= -f2-)
printf '%s' "$OPENAI_KEY" | gcloud secrets create openai-api-key \
  --data-file=- --project="$PROJECT_ID" 2>&1 || \
  printf '%s' "$OPENAI_KEY" | gcloud secrets versions add openai-api-key \
  --data-file=- --project="$PROJECT_ID"

printf '%s' "$DB_PASS" | gcloud secrets create db-password \
  --data-file=- --project="$PROJECT_ID" 2>&1 || \
  printf '%s' "$DB_PASS" | gcloud secrets versions add db-password \
  --data-file=- --project="$PROJECT_ID"

# ── 5. Artifact Registry ──────────────────────────────────────────────────────
echo ""
echo "==> Artifact Registry..."
gcloud artifacts repositories create cloud-run-source-deploy \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" --quiet 2>&1 || true

# ── 6. Build & Push ───────────────────────────────────────────────────────────
echo ""
echo "==> Auth Docker..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Build Docker (linux/amd64)..."
cd "$(dirname "$0")"
docker build --platform linux/amd64 -t "$IMAGE" .

echo "==> Push vers Artifact Registry..."
docker push "$IMAGE"

# ── 7. Permissions ────────────────────────────────────────────────────────────
echo ""
echo "==> Permissions IAM..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" --quiet

# ── 8. Deploy Cloud Run ───────────────────────────────────────────────────────
echo ""
echo "==> Déploiement Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --project "$PROJECT_ID" \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest,DB_PASS=db-password:latest" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=${SQL_CONNECTION},DB_USER=whisperer,DB_NAME=whisperer" \
  --add-cloudsql-instances="$SQL_CONNECTION" \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5

echo ""
echo "==> Déployé !"
URL=$(gcloud run services describe "$SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "==> URL : $URL"
