#!/bin/bash
# push.sh — Build local + push Artifact Registry + deploy Cloud Run
# Usage : bash push.sh

set -e

PROJECT_ID="whisperer-perso"
REGION="europe-west1"
SERVICE="whisperer"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:whisperer-db"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE}:latest"

cd "$(dirname "$0")"

echo "==> Auth Docker → Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Build Docker (local)..."
docker build --platform linux/amd64 -t "$IMAGE" .

echo "==> Push vers Artifact Registry..."
docker push "$IMAGE"

echo "==> Deploy Cloud Run depuis l'image..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --project "$PROJECT_ID" \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest,DB_PASS=db-password:latest,ADMIN_TOKEN=admin-token:latest" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=${SQL_CONNECTION},DB_USER=whisperer,DB_NAME=whisperer" \
  --add-cloudsql-instances="$SQL_CONNECTION" \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5

echo ""
echo "==> Déployé !"
gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)"
