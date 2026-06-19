# StoryForge VPS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the StoryForge FastAPI app to `wf.belghitis.com` on a Hostinger VPS via Docker + GitHub Actions CI/CD.

**Architecture:** Docker image built in GitHub Actions → pushed to GHCR (private) → SSH into VPS → docker compose pull + up. nginx (host) reverse-proxies `wf.belghitis.com:443` → `127.0.0.1:8001`. Named volumes persist generated images, templates, storefront SQLite DB, and book configs across deploys.

**Tech Stack:** Python 3.11-slim Docker, uvicorn (direct, no reload), nginx, Let's Encrypt SSL, GitHub Actions, GHCR (private registry), docker-compose v2.

## Global Constraints

- Port 8001 on VPS (Next.js = 3000, n8n = 5678 — must not conflict)
- `uvicorn` run directly (NOT via `python3 dashboard/app.py`) — bypasses `reload=True` in `__main__`
- `python3 -u` NOT needed when running uvicorn directly (only needed for subprocess spawning)
- `settings.json` is gitignored — VPS manages its own copy via bind mount
- GHCR image is private (repo is private) — VPS must already have `docker login ghcr.io` done (one-time manual setup)
- Never commit `.env`, `.env.local`, or `settings.json`
- `app_dir` for uvicorn is `/app` (WORKDIR in Docker) — `dashboard.app:app` resolves from there

---

### Task 1: Fix requirements.txt + Dockerfile + .dockerignore

**Files:**
- Modify: `requirements.txt`
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Produces: Docker image `ghcr.io/mouad1/kidp:latest` buildable locally and in CI

- [ ] **Step 1: Replace requirements.txt with complete dependency list**

Current `requirements.txt` only has `stripe`. Replace entirely:

```
fastapi==0.135.3
uvicorn[standard]==0.44.0
pillow==12.2.0
img2pdf==0.6.3
jinja2==3.1.6
stripe==15.2.0
httpx==0.28.1
google-genai==1.73.0
python-multipart==0.0.26
pydantic==2.12.5
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN useradd -m -u 1001 appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Why `uvicorn` directly (not `python3 dashboard/app.py`):** The `__main__` block in `app.py` hardcodes `reload=True`. Hot-reload in production would restart the server whenever any file changes, breaking long-running SSE image generation streams. Running uvicorn directly skips that block entirely.

- [ ] **Step 3: Create .dockerignore**

```
.git/
.env.local
.env
node_modules/
output/
images/
__pycache__/
**/__pycache__/
*.pyc
*.pyo
.venv/
*.xlsx
*.csv
books/*/hero/source_*.png
books/*/hero/canonical_portrait.png
books/*/hero/cover.png
storyforge/templates/
.storefront/
```

`images/` excluded — large generated PNGs, served from Docker volume. Hero source PNGs excluded — large binaries not needed at runtime. `storyforge/templates/` excluded — orphaned directory (old wrong path, now `templates/` is correct).

- [ ] **Step 4: Build Docker image locally to verify**

```bash
docker build -t kidp-local .
```

Expected: build completes with no errors. Final line: `Successfully built <hash>` or `writing image sha256:...`

- [ ] **Step 5: Run container locally to verify app starts**

```bash
docker run --rm -p 8002:8000 \
  -e GEMINI_API_KEY="" \
  -e STOREFRONT_SESSION_SECRET="test-secret-local" \
  -e STOREFRONT_SMTP_HOST="" \
  -e STOREFRONT_SMTP_PORT="587" \
  -e STOREFRONT_SMTP_USERNAME="" \
  -e STOREFRONT_SMTP_PASSWORD="" \
  -e STOREFRONT_SMTP_FROM_ADDR="test@example.com" \
  -e RESEND_API_KEY="" \
  -e STRIPE_SECRET_KEY="" \
  -e STRIPE_WEBHOOK_SECRET="" \
  kidp-local
```

Expected output contains: `Uvicorn running on http://0.0.0.0:8000`

Check: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/` → `200` or `302`

Stop with Ctrl+C.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt Dockerfile .dockerignore
git commit -m "feat(deploy): add Dockerfile, fix requirements.txt, add .dockerignore"
```

---

### Task 2: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: `ghcr.io/mouad1/kidp:latest` image from Task 1
- Produces: `docker compose up -d` launches container on `127.0.0.1:8001`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  storyforge:
    image: ghcr.io/mouad1/kidp:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8001:8000"
    env_file: .env
    volumes:
      - storyforge_images:/app/images
      - storyforge_templates:/app/templates
      - storyforge_storefront:/app/.storefront
      - storyforge_books:/app/books
      - /home/storyforge/settings.json:/app/settings.json

volumes:
  storyforge_images:
  storyforge_templates:
  storyforge_storefront:
  storyforge_books:
```

**Volume notes:**
- Named volumes (`storyforge_*`) are seeded from image content on first creation, then persist across deploys.
- `settings.json` uses a bind mount — named volumes create a directory, not a file, when the path is a file.
- No `storyforge_settings` named volume declared because it's a bind mount.

- [ ] **Step 2: Validate compose syntax**

```bash
docker compose config
```

Expected: prints fully resolved YAML with no errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): add docker-compose.yml with volumes and port mapping"
```

---

### Task 3: nginx config

**Files:**
- Create: `deploy/nginx.conf`

**Interfaces:**
- Produces: nginx server block for `wf.belghitis.com` → `127.0.0.1:8001`

- [ ] **Step 1: Create deploy/ directory and nginx.conf**

```bash
mkdir -p deploy
```

Create `deploy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name wf.belghitis.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name wf.belghitis.com;

    ssl_certificate /etc/letsencrypt/live/wf.belghitis.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wf.belghitis.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

`client_max_body_size 20M` — photo upload (face-swap feature) requires it.
`proxy_buffering off` + `proxy_read_timeout 300s` — SSE streaming for image generation (can take minutes).

- [ ] **Step 2: Commit**

```bash
git add deploy/nginx.conf
git commit -m "feat(deploy): add nginx config for wf.belghitis.com"
```

---

### Task 4: GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: all files from Tasks 1–3
- Produces: automated deploy on every push to `main`

- [ ] **Step 1: Create .github/workflows/ directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create .github/workflows/deploy.yml**

```yaml
name: Deploy StoryForge

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ghcr.io/mouad1/kidp:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            set -e
            cd /home/storyforge
            git pull origin main

            printf 'GEMINI_API_KEY=%s\n' '${{ secrets.GEMINI_API_KEY }}' > .env
            printf 'STOREFRONT_SESSION_SECRET=%s\n' '${{ secrets.STOREFRONT_SESSION_SECRET }}' >> .env
            printf 'STOREFRONT_SMTP_HOST=%s\n' '${{ secrets.STOREFRONT_SMTP_HOST }}' >> .env
            printf 'STOREFRONT_SMTP_PORT=%s\n' '${{ secrets.STOREFRONT_SMTP_PORT }}' >> .env
            printf 'STOREFRONT_SMTP_USERNAME=%s\n' '${{ secrets.STOREFRONT_SMTP_USERNAME }}' >> .env
            printf 'STOREFRONT_SMTP_PASSWORD=%s\n' '${{ secrets.STOREFRONT_SMTP_PASSWORD }}' >> .env
            printf 'STOREFRONT_SMTP_FROM_ADDR=%s\n' '${{ secrets.STOREFRONT_SMTP_FROM_ADDR }}' >> .env
            printf 'RESEND_API_KEY=%s\n' '${{ secrets.RESEND_API_KEY }}' >> .env
            printf 'STRIPE_SECRET_KEY=%s\n' '${{ secrets.STRIPE_SECRET_KEY }}' >> .env
            printf 'STRIPE_WEBHOOK_SECRET=%s\n' '${{ secrets.STRIPE_WEBHOOK_SECRET }}' >> .env

            test -f settings.json || cp settings.example.json settings.json

            sudo cp deploy/nginx.conf /etc/nginx/sites-available/storyforge
            sudo ln -sf /etc/nginx/sites-available/storyforge /etc/nginx/sites-enabled/storyforge
            sudo nginx -t
            sudo nginx -s reload

            docker compose pull
            docker compose up -d --remove-orphans
            docker image prune -f
```

**Why `printf` not heredoc:** heredoc with `${{ secrets.XXX }}` substituted by GitHub Actions can break if a secret value contains special shell characters. `printf '%s\n'` is safe for any value content.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(deploy): add GitHub Actions CI/CD workflow for VPS deploy"
```

---

### Task 5: GitHub Secrets + first deploy + VPS settings

**Files:**
- No code files — GitHub UI + SSH into VPS

**Interfaces:**
- Consumes: all files pushed to `main` from Tasks 1–4
- Produces: live app at `https://wf.belghitis.com`

- [ ] **Step 1: Add GitHub Secrets**

Go to: `https://github.com/Mouad1/kidp/settings/secrets/actions`

Add these secrets (Settings → Secrets and variables → Actions → New repository secret):

**Infra:**
| Secret | Value |
|---|---|
| `VPS_HOST` | VPS IP or hostname |
| `VPS_USER` | SSH username (e.g. `root`) |
| `VPS_SSH_KEY` | Private key content (e.g. contents of `~/.ssh/id_ed25519`) |

**App (copy from .env.local):**
| Secret |
|---|
| `GEMINI_API_KEY` |
| `STOREFRONT_SESSION_SECRET` |
| `STOREFRONT_SMTP_HOST` |
| `STOREFRONT_SMTP_PORT` |
| `STOREFRONT_SMTP_USERNAME` |
| `STOREFRONT_SMTP_PASSWORD` |
| `STOREFRONT_SMTP_FROM_ADDR` |
| `RESEND_API_KEY` |
| `STRIPE_SECRET_KEY` |
| `STRIPE_WEBHOOK_SECRET` |

- [ ] **Step 2: Push to main to trigger first deploy**

```bash
git push origin main
```

Watch: `https://github.com/Mouad1/kidp/actions` — the `Deploy StoryForge` workflow should appear and run.

Expected: all steps green. Final step "Deploy to VPS" completes without `set -e` exit.

- [ ] **Step 3: Configure settings.json on VPS (SSH in)**

After first deploy, the script created `/home/storyforge/settings.json` from `settings.example.json`. Edit it for production:

```bash
ssh <VPS_USER>@<VPS_HOST>
nano /home/storyforge/settings.json
```

Change these values:

```json
{
  "storefront": {
    "https": true,
    "admin": {
      "enabled": true,
      "emails": ["belghiti.mouad.1@gmail.com"]
    },
    "payment_provider": "stripe"
  }
}
```

Then restart the container to pick up the new settings:

```bash
cd /home/storyforge
docker compose restart storyforge
```

**Why these changes:**
- `https: true` → session cookies get `Secure` flag (required behind HTTPS proxy, broken without it)
- `admin.enabled: true` → enables OTP email auth for `/admin` routes
- `payment_provider: "stripe"` → uses live Stripe instead of stub

- [ ] **Step 4: Verify app is live**

```bash
curl -I https://wf.belghitis.com/
```

Expected: `HTTP/2 200` or `HTTP/2 302`

```bash
curl -I https://wf.belghitis.com/store
```

Expected: `HTTP/2 200`

- [ ] **Step 5: Update Stripe webhook endpoint**

Go to: Stripe Dashboard → Developers → Webhooks → Add endpoint

```
Endpoint URL: https://wf.belghitis.com/webhook/stripe
Events: payment_intent.succeeded, checkout.session.completed
```

Save the new webhook signing secret. Update `STRIPE_WEBHOOK_SECRET` GitHub Secret to the new value. Push a dummy commit to trigger redeploy with the new secret:

```bash
git commit --allow-empty -m "chore: trigger redeploy with updated stripe webhook secret"
git push origin main
```

- [ ] **Step 6: Smoke test storefront end-to-end**

1. Visit `https://wf.belghitis.com/store` — catalog should show `coiffeur-roi`
2. Click story → preview page renders (2-column, no scroll)
3. Visit `https://wf.belghitis.com/admin` — OTP email flow should send to `belghiti.mouad.1@gmail.com`
4. Log into admin → `/admin/stories` shows `coiffeur-roi`

---

## Self-Review

**Spec coverage:**
- ✅ Docker image + Dockerfile
- ✅ requirements.txt fixed
- ✅ docker-compose.yml with all 5 volumes
- ✅ nginx config with SSE + upload support
- ✅ GitHub Actions workflow with 13 secrets
- ✅ One-time VPS setup documented (Task 5)
- ✅ Stripe webhook update
- ✅ settings.json prod configuration (https=true, payment_provider=stripe, admin=true)
- ✅ `uvicorn` direct (no reload) — critical constraint

**No placeholders found.**

**Type/name consistency:** `storyforge_images`, `storyforge_templates`, `storyforge_storefront`, `storyforge_books` used consistently across docker-compose.yml and volume table in spec. Port 8001 consistent throughout.
