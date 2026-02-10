# Deployment Checklist (Docker) - Railway, Render, Fly.io

Use this as an execution runbook.

## Prerequisites

1. Repo is pushed to GitHub/GitLab and includes:
- `Dockerfile`
- `requirements.txt`
- `src/`

2. Required secrets ready:
- `SIGTRIP_API_KEY`

3. Recommended env values:
- `MCP_HOST=0.0.0.0`
- `MCP_PORT=8000`
- `APP_ENV=prod`
- `APP_VERSION=<release-tag>`
- Optional: `SIGTRIP_UPSTREAM_URL=https://hotel.sigtrip.ai/mcp`

4. Local smoke check (before deploy):

```bash
cd /Users/workhard/Desktop/research/mcp
docker build -t sigtrip-wrapper:local .
docker run --rm -p 8000:8000 --env-file .env sigtrip-wrapper:local
```

Quick checks:
- `http://localhost:8000/healthz`
- `http://localhost:8000/readyz`

---

## Option A: Railway (Docker)

## 1. Create service
1. Log in to Railway dashboard.
2. Create `New Project`.
3. Choose `Deploy from GitHub repo` and select this repository.
4. Select the service root (repo root where `Dockerfile` is located).

## 2. Build/start config
1. Railway auto-detects `Dockerfile`.
2. Ensure service uses Docker build path from repo root.
3. Start command is from Docker image `CMD` (`python -m src.server`) unless explicitly overridden.

## 3. Variables
In service variables, add:
- `SIGTRIP_API_KEY`
- `MCP_HOST=0.0.0.0`
- `MCP_PORT=8000`
- `APP_ENV=prod`
- `APP_VERSION=<release-tag>`
- Optional `SIGTRIP_UPSTREAM_URL`

## 4. Network/domain
1. Open service `Settings` -> networking/public domain.
2. Enable public domain.
3. Confirm HTTPS URL is generated.

## 5. Health checks
1. Set health check path to `/healthz` if Railway health check config is enabled.
2. Redeploy if required.

## 6. Verify
Run:

```bash
cd /Users/workhard/Desktop/research/mcp
./scripts/post_deploy_verify.sh https://<railway-domain>
```

---

## Option B: Render (Docker Web Service)

## 1. Create service
1. Log in to Render dashboard.
2. Click `New` -> `Web Service`.
3. Connect repository and select this repo.

## 2. Build/start config
1. Environment: `Docker`.
2. Docker context/root: repo root.
3. If prompted for command, leave blank to use Docker `CMD`.

## 3. Variables
In `Environment` section, add:
- `SIGTRIP_API_KEY`
- `MCP_HOST=0.0.0.0`
- `MCP_PORT=8000`
- `APP_ENV=prod`
- `APP_VERSION=<release-tag>`
- Optional `SIGTRIP_UPSTREAM_URL`

## 4. Health check
Set `Health Check Path` to:
- `/healthz`

## 5. Deploy
1. Create Web Service.
2. Wait for build + deploy logs to pass.
3. Open service URL.

## 6. Verify
Run:

```bash
cd /Users/workhard/Desktop/research/mcp
./scripts/post_deploy_verify.sh https://<render-domain>
```

---

## Option C: Fly.io (Docker)

## 1. Install and login

```bash
brew install flyctl
fly auth login
```

## 2. Create app config from repo
From repo root:

```bash
cd /Users/workhard/Desktop/research/mcp
fly launch --no-deploy
```

During prompts:
- App name: choose unique name
- Region: choose closest to users
- Use existing `Dockerfile`: yes

This creates `fly.toml`.

## 3. Configure app
In `fly.toml`, ensure:
- internal port is `8000`
- HTTP service enabled
- health checks point to `/healthz`

Example essentials:

```toml
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true

[[http_service.checks]]
  grace_period = "10s"
  interval = "30s"
  timeout = "5s"
  method = "GET"
  path = "/healthz"
```

## 4. Set secrets

```bash
fly secrets set SIGTRIP_API_KEY=<value> APP_ENV=prod APP_VERSION=<release-tag> MCP_HOST=0.0.0.0 MCP_PORT=8000
```

Optional:

```bash
fly secrets set SIGTRIP_UPSTREAM_URL=https://hotel.sigtrip.ai/mcp
```

## 5. Deploy

```bash
fly deploy
```

## 6. Verify
Get app URL then run:

```bash
cd /Users/workhard/Desktop/research/mcp
./scripts/post_deploy_verify.sh https://<fly-domain>
```

---

## Manual security steps (all platforms)

1. Restrict who can call public MCP endpoint (`/sse`) using edge auth/API gateway/token.
2. Add rate limiting at platform edge or proxy.
3. Avoid logging secrets and PII.
4. Rotate `SIGTRIP_API_KEY` on schedule.

---

## Final MCP verification (all platforms)

After `post_deploy_verify.sh` passes:

1. Open MCP Inspector.
2. Connect with transport `SSE` to `https://<domain>/sse`.
3. Run `tools/list`.
4. Run:
- `plan_hotel_options` with `{"query":"Show me hotels in Denver"}`
- `compare_hotels_from_query` with `{"query":"Compare hotels in Denver for 2 guests"}`
- `create_booking_request` with valid `offer_id` + guest payload

Acceptance criteria:
- Tools return structured JSON
- `price_preview.from_total` present when offers available
- `compare` tools return ranked output
- Booking request returns payment link or structured error
