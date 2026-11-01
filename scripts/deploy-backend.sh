#!/usr/bin/env bash
# Deploy the Kettu API to Google Cloud Run (Mumbai), one instance, secrets from Secret Manager.
# Usage: PROJECT=my-gcp-project WEB_ORIGIN=https://kettu.vercel.app ./scripts/deploy-backend.sh
#
# One-time: create the secrets (values are read from your shell, never committed):
#   printf %s "$GNANI_API_KEY"        | gcloud secrets create kettu-gnani-key --data-file=-
#   printf %s "$ANTHROPIC_API_KEY"    | gcloud secrets create kettu-anthropic-key --data-file=-
#   printf %s "$SUPABASE_SERVICE_KEY" | gcloud secrets create kettu-supabase-key --data-file=-
#   printf %s "$WA_ACCESS_TOKEN"      | gcloud secrets create kettu-wa-token --data-file=-
#   printf %s "$WA_APP_SECRET"        | gcloud secrets create kettu-wa-app-secret --data-file=-
set -euo pipefail

: "${PROJECT:?set PROJECT}"
: "${WEB_ORIGIN:?set WEB_ORIGIN (your Vercel URL)}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-kettu-api}"
cd "$(dirname "$0")/../backend"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --source . \
  --allow-unauthenticated \
  --cpu 2 --memory 2Gi --concurrency 40 --timeout 300 \
  --min-instances 1 --max-instances 1 \
  --set-env-vars "LLM_PROVIDER=anthropic,ANTHROPIC_MODEL=claude-haiku-5-5,CORS_ORIGINS=${WEB_ORIGIN},PUBLIC_APP_URL=${WEB_ORIGIN},SUPABASE_URL=${SUPABASE_URL:-},WA_PHONE_NUMBER_ID=${WA_PHONE_NUMBER_ID:-},WA_VERIFY_TOKEN=${WA_VERIFY_TOKEN:-},WA_ALLOWED_NUMBERS=${WA_ALLOWED_NUMBERS:-},WA_HASH_SALT=${WA_HASH_SALT:-change-me}" \
  --set-secrets "GNANI_API_KEY=kettu-gnani-key:latest,ANTHROPIC_API_KEY=kettu-anthropic-key:latest,SUPABASE_SERVICE_KEY=kettu-supabase-key:latest,WA_ACCESS_TOKEN=kettu-wa-token:latest,WA_APP_SECRET=kettu-wa-app-secret:latest"

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')
echo "API: $URL"
curl -fsS "$URL/healthz?deep=1" && echo
echo "WhatsApp webhook URL: $URL/whatsapp/webhook"
