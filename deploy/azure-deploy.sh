# ================================================================
# Azure Container Apps — Infrastructure as Code
# Deploy the AI Data Analyst backend in one script.
#
# Prerequisites (one-time):
#   az login
#   az extension add --name containerapp --upgrade
#
# Usage:
#   chmod +x deploy/azure-deploy.sh
#   ./deploy/azure-deploy.sh
# ================================================================

set -euo pipefail

# ── Config (override via env vars or edit here) ─────────────────
RESOURCE_GROUP="${RESOURCE_GROUP:-ai-data-analyst-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-aidataanalystacr}"          # must be globally unique
APP_ENV_NAME="${APP_ENV_NAME:-ai-data-analyst-env}"
APP_NAME="${APP_NAME:-ai-data-analyst-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# ── LLM / App secrets (set these before running!) ───────────────
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY}"
OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
MODEL="${MODEL:-gpt-4.1-nano}"
GROQ_API_KEY="${GROQ_API_KEY:-}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-*}"

echo "▶ Resource Group: $RESOURCE_GROUP ($LOCATION)"
echo "▶ ACR: $ACR_NAME"
echo "▶ Container App: $APP_NAME"

# ── 1. Resource group ────────────────────────────────────────────
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none
echo "✓ Resource group ready"

# ── 2. Azure Container Registry ──────────────────────────────────
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none 2>/dev/null || echo "  (ACR already exists)"

ACR_SERVER="${ACR_NAME}.azurecr.io"
ACR_CREDS=$(az acr credential show --name "$ACR_NAME" --output json)
ACR_USER=$(echo "$ACR_CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
ACR_PASS=$(echo "$ACR_CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['passwords'][0]['value'])")
echo "✓ ACR ready: $ACR_SERVER"

# ── 3. Build & push image ─────────────────────────────────────────
IMAGE_FULL="${ACR_SERVER}/${APP_NAME}:${IMAGE_TAG}"

# Build from repo root (where Dockerfile lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

az acr build \
  --registry "$ACR_NAME" \
  --image "${APP_NAME}:${IMAGE_TAG}" \
  --file "$REPO_ROOT/Dockerfile" \
  "$REPO_ROOT" \
  --output none
echo "✓ Image built & pushed: $IMAGE_FULL"

# ── 4. Container Apps Environment ────────────────────────────────
az containerapp env create \
  --name "$APP_ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none 2>/dev/null || echo "  (Environment already exists)"
echo "✓ Container Apps environment ready"

# ── 5. Deploy / update the Container App ─────────────────────────
# Check if app already exists
if az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "  Updating existing Container App..."
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$IMAGE_FULL" \
    --set-env-vars \
      "OPENAI_API_KEY=secretref:openai-api-key" \
      "OPENAI_BASE_URL=$OPENAI_BASE_URL" \
      "MODEL=$MODEL" \
      "GROQ_API_KEY=$GROQ_API_KEY" \
      "ALLOWED_ORIGINS=$ALLOWED_ORIGINS" \
      "LLM_BUDGET_US=5.0" \
      "LLM_MIN_INTERVAL_S=0.5" \
      "ENABLE_PDF=0" \
      "OUTPUT_ROOT=/app/output" \
      "UPLOAD_DIR=/app/uploads" \
    --output none
else
  echo "  Creating new Container App..."
  az containerapp create \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$APP_ENV_NAME" \
    --image "$IMAGE_FULL" \
    --registry-server "$ACR_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 3 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --env-vars \
      "OPENAI_API_KEY=secretref:openai-api-key" \
      "OPENAI_BASE_URL=$OPENAI_BASE_URL" \
      "MODEL=$MODEL" \
      "GROQ_API_KEY=$GROQ_API_KEY" \
      "ALLOWED_ORIGINS=$ALLOWED_ORIGINS" \
      "LLM_BUDGET_US=5.0" \
      "LLM_MIN_INTERVAL_S=0.5" \
      "ENABLE_PDF=0" \
      "OUTPUT_ROOT=/app/output" \
      "UPLOAD_DIR=/app/uploads" \
    --secrets "openai-api-key=$OPENAI_API_KEY" \
    --output none
fi
echo "✓ Container App deployed"

# ── 6. Get the public URL ─────────────────────────────────────────
APP_URL=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅  Deployment complete!                            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  API URL  : https://${APP_URL}"
echo "║  Health   : https://${APP_URL}/health"
echo "║  Docs     : https://${APP_URL}/docs"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Next step: set VITE_API_BASE_URL=https://${APP_URL} in Vercel"
