# Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  User                                                   │
│    │                                                    │
│    ▼                                                    │
│  Vercel (Frontend · React/Vite)                        │
│    │  VITE_API_BASE_URL=https://api.azurecontainerapps │
│    │                                                    │
│    ▼                                                    │
│  Azure Container Apps (Backend · FastAPI)              │
│    │  scales 0 → 3 replicas based on HTTP load         │
│    │  secrets via Azure Container Apps Secrets         │
│    │                                                    │
│    ▼                                                    │
│  Azure Container Registry (ACR)                        │
│    stores Docker image                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Part 1 — Backend on Azure Container Apps

### Why Azure Container Apps?
| Feature | Benefit |
|---|---|
| Scale to zero | Free when idle — no idle VM cost |
| Up to 300s request timeout | Supports the 5-min analysis pipeline |
| Built-in HTTPS/TLS | No cert management |
| Managed secrets | API keys stored safely |
| `az acr build` | Builds image in the cloud — no local Docker needed |

---

### One-Time Azure Setup

#### 1. Install Azure CLI
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az extension add --name containerapp --upgrade
```

#### 2. Login & set subscription
```bash
az login
az account set --subscription "<your-subscription-id>"
```

#### 3. Create a Service Principal (for GitHub Actions CI/CD)
```bash
az ad sp create-for-rbac \
  --name "ai-data-analyst-sp" \
  --role contributor \
  --sdk-auth \
  --scopes /subscriptions/<your-subscription-id>
```
Copy the JSON output — you'll add it as the `AZURE_CREDENTIALS` GitHub secret.

---

### Manual Deploy (first time or one-shot)

```bash
# Set required env vars
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"   # or NVIDIA NIM URL
export MODEL="gpt-4.1-nano"
export GROQ_API_KEY="your-groq-key"           # optional fallback
export ALLOWED_ORIGINS="https://your-app.vercel.app"

# Run the deploy script
chmod +x deploy/azure-deploy.sh
./deploy/azure-deploy.sh
```

The script prints the API URL at the end — copy it for Vercel.

---

### GitHub Actions (automatic on push)

Add these **GitHub Repository Secrets** (`Settings → Secrets → Actions`):

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | Full JSON from `az ad sp create-for-rbac` |
| `OPENAI_API_KEY` | Your OpenAI / NVIDIA NIM API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` or NVIDIA endpoint |
| `MODEL` | `gpt-4.1-nano` (or your preferred model) |
| `GROQ_API_KEY` | Groq key (optional fallback) |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |

Then push to `main` — the workflow in `.github/workflows/deploy-backend.yml` runs automatically.

---

### Update `ALLOWED_ORIGINS` after Vercel deploy

Once you have the Vercel URL, update the Container App:
```bash
az containerapp update \
  --name ai-data-analyst-api \
  --resource-group ai-data-analyst-rg \
  --set-env-vars "ALLOWED_ORIGINS=https://your-app.vercel.app"
```

---

## Part 2 — Frontend on Vercel

### 1. Push frontend to GitHub
The `frontend/` directory is already in your repo. Make sure it's committed.

### 2. Import project on Vercel
1. Go to [vercel.com/new](https://vercel.com/new)
2. Import `kamalesh346/data_analyst_agent`
3. Set **Root Directory** → `frontend`
4. Vercel auto-detects **Vite** from `vercel.json`

### 3. Add environment variable

| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<your-container-app>.azurecontainerapps.io` |

### 4. Deploy
Click **Deploy** — Vercel builds and publishes. Every push to `main` auto-redeploys.

---

## Part 3 — CORS Wiring

The backend reads `ALLOWED_ORIGINS` and sets CORS headers. After Vercel gives you a URL like `https://ai-data-analyst-abc123.vercel.app`:

```bash
# Backend: allow only your Vercel domain
az containerapp update \
  --name ai-data-analyst-api \
  --resource-group ai-data-analyst-rg \
  --set-env-vars "ALLOWED_ORIGINS=https://ai-data-analyst-abc123.vercel.app"
```

```
# Frontend Vercel env var:
VITE_API_BASE_URL=https://ai-data-analyst-api.<hash>.eastus.azurecontainerapps.io
```

---

## Part 4 — Verify Deployment

```bash
# Health check
curl https://<your-app>.azurecontainerapps.io/health

# Test analyze endpoint
curl -X POST https://<your-app>.azurecontainerapps.io/analyze \
  -F "file=@data/sample_sales.csv"
```

---

## Cost Estimate (Azure)

| Resource | Tier | Est. Monthly |
|---|---|---|
| Azure Container Registry | Basic | ~$5 |
| Container Apps (1 vCPU, 2 GB) | Consumption (scale-to-zero) | ~$0–15 depending on usage |
| Total | | **~$5–20/month** |

> Vercel Hobby plan is **free** for personal projects.

---

## Useful Commands

```bash
# View logs
az containerapp logs show \
  --name ai-data-analyst-api \
  --resource-group ai-data-analyst-rg \
  --follow

# Scale to zero manually (pause)
az containerapp update \
  --name ai-data-analyst-api \
  --resource-group ai-data-analyst-rg \
  --min-replicas 0 --max-replicas 0

# Delete everything (teardown)
az group delete --name ai-data-analyst-rg --yes --no-wait
```
