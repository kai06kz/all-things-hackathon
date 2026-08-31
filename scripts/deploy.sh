#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to your Google Cloud project ID.}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-knowledge-rag}"

gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --remove-secrets GEMINI_API_KEY \
  --min-instances 1 \
  --max-instances 10 \
  --concurrency 80 \
  --memory 1Gi \
  --timeout 120