# StoryForge Deployment Design — wf.belghitis.com

**Date:** 2026-06-19  
**Branch:** main (post-merge feat/admin-story-pipeline)  
**Target:** Hostinger VPS, subdomain `wf.belghitis.com`

---

## Context

StoryForge is a FastAPI/uvicorn app (dashboard/app.py, port 8000) for managing personalized children's storybook production and an end-customer storefront. The VPS already runs nginx (host) + Docker Compose for belghitis.com (Next.js) and n8n.belghitis.com. This deployment follows the same pattern for consistency.

---

## Architecture

```
GitHub push → main
      ↓
GitHub Actions (.github/workflows/deploy.yml)
  1. Build Docker image → push ghcr.io/mouad1/kidp:latest
  2. SSH into VPS
  3. git pull /home/storyforge
  4. Recreate .env from GitHub Secrets
  5. Copy deploy/nginx.conf → /etc/nginx/sites-available/storyforge
  6. nginx -t && nginx -s reload
  7. docker compose pull && docker compose up -d --remove-orphans
  8. docker image prune -f

VPS (host)
  nginx:443  wf.belghitis.com  (SSL via Let's Encrypt)
      ↓ proxy_pass  http://127.0.0.1:8001
  Docker container: ghcr.io/mouad1/kidp
    FastAPI/uvicorn on :8000 (mapped to host :8001)
      ↓
  Named Docker volumes (persistent across deploys)
```

---

## Files to Create

| File | Purpose |
|---|---|
| `Dockerfile` | Python 3.11-slim image, installs requirements, runs dashboard/app.py |
| `docker-compose.yml` | Single `storyforge` service, port mapping, env_file, volumes |
| `deploy/nginx.conf` | nginx server block for wf.belghitis.com |
| `.github/workflows/deploy.yml` | Full CI/CD pipeline |
| `requirements.txt` | Fixed — was missing most dependencies |

---

## Dockerfile

Base: `python:3.11-slim`. Non-root user `appuser`. Copies full repo, installs requirements, exposes 8000.

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
CMD ["python3", "-u", "dashboard/app.py"]
```

The `-u` flag (unbuffered) is required — app uses SSE streaming and was previously broken without it.

---

## requirements.txt (complete)

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

---

## docker-compose.yml

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
      - /home/storyforge/settings.json:/app/settings.json  # bind mount (named volume breaks on single file)

volumes:
  storyforge_images:
  storyforge_templates:
  storyforge_storefront:
  storyforge_books:
```

Port 8001 chosen to avoid conflict with existing services (3000 = Next.js, 5678 = n8n).

---

## Persistent Volumes

| Volume | Container path | Content | Why persistent |
|---|---|---|---|
| `storyforge_images` | `/app/images` | AI-generated PNG images | Large, runtime-generated, expensive to regenerate |
| `storyforge_templates` | `/app/templates` | Published story templates | Admin-created via dashboard |
| `storyforge_storefront` | `/app/.storefront` | `storefront.db` SQLite (orders, auth) | Customer orders must survive deploys |
| `storyforge_books` | `/app/books` | Book configs (config.py per book) | Admin can create new books |
| bind mount `/home/storyforge/settings.json` | `/app/settings.json` | App settings (SMTP, auth toggle, etc.) | Modifiable via dashboard at runtime |

**Note:** `settings.json` uses a bind mount (not a named volume) because Docker named volumes on single files create a directory. Deploy script guards: `test -f /home/storyforge/settings.json || cp /home/storyforge/settings.example.json /home/storyforge/settings.json`. Never overwritten by `git pull` after first init.

---

## nginx Config (deploy/nginx.conf)

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

        # SSE streaming support (image generation can take minutes)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

`client_max_body_size 20M` needed for photo uploads (face-swap feature).

---

## GitHub Actions Workflow (.github/workflows/deploy.yml)

Trigger: push to `main`.

Steps:
1. Checkout
2. Login to GHCR with `GITHUB_TOKEN`
3. Build + push image with GHA cache
4. SSH into VPS (appleboy/ssh-action):
   - `cd /home/storyforge && git pull origin main`
   - Write `.env` from secrets (heredoc)
   - Init `settings.json` if not present
   - Copy nginx conf → symlink → `nginx -t && nginx -s reload`
   - `docker compose pull && docker compose up -d --remove-orphans`
   - `docker image prune -f`

---

## GitHub Secrets Required

**Infra (3):**
```
VPS_HOST          # IP or hostname of the VPS
VPS_USER          # SSH user (e.g. root or deploy)
VPS_SSH_KEY       # Private SSH key (ed25519 recommended)
```

**App (10 — mirrors .env.local):**
```
GEMINI_API_KEY
STOREFRONT_SESSION_SECRET
STOREFRONT_SMTP_HOST
STOREFRONT_SMTP_PORT
STOREFRONT_SMTP_USERNAME
STOREFRONT_SMTP_PASSWORD
STOREFRONT_SMTP_FROM_ADDR
RESEND_API_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

---

## One-Time VPS Setup (manual, before first deploy)

```bash
# 1. Add DNS A record: wf.belghitis.com → VPS IP (Hostinger panel)
#    Wait for propagation before certbot

# 2. Obtain SSL certificate
certbot certonly --nginx -d wf.belghitis.com

# 3. Clone repo
git clone https://github.com/Mouad1/kidp.git /home/storyforge

# 4. Authenticate Docker with GHCR (private repo = private image)
echo "<GITHUB_PAT>" | docker login ghcr.io --username Mouad1 --password-stdin
# PAT needs: read:packages scope. Create at github.com/settings/tokens

# 5. Init settings.json (once)
cp /home/storyforge/settings.example.json /home/storyforge/settings.json
# Edit as needed (Stripe live keys, SMTP, etc.)
```

GitHub Actions handles everything after that.

---

## Stripe Webhook Update

After deploy, update Stripe webhook endpoint from local to:
```
https://wf.belghitis.com/webhook/stripe
```

---

## Constraints

- Port 8001 must be free on VPS (Next.js uses 3000, n8n uses 5678).
- `python3 -u` flag mandatory — SSE streaming breaks without unbuffered output.
- uvicorn `reload=True` is disabled in prod (only local dev needs hot-reload). The app already conditionally sets `reload` based on env — verify this is off in prod.
- Docker image is public on GHCR by default for public repos; private repo = authenticated pull needed on VPS (`docker login ghcr.io`).
