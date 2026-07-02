# Production Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the realestate-agentic platform to production with HTTPS, managed database, secure secrets, and CI/CD pipeline.

**Architecture:** VPS (Ubuntu) running Docker Compose with Caddy reverse proxy for automatic HTTPS. PostgreSQL on managed service (Supabase or Neon). Redis on the VPS. GitHub Actions for CI/CD.

**Tech Stack:** Docker, Caddy, GitHub Actions, Supabase (DB + Auth), Redis, Let's Encrypt (via Caddy)

---

## Infrastructure Overview

```
Internet
   |
   v
[Caddy Reverse Proxy] :443 (HTTPS, auto Let's Encrypt)
   |
   +---> /api/*  --> [FastAPI Backend] :8000 (gunicorn + uvicorn workers)
   +---> /ws/*   --> [FastAPI Backend] :8000 (WebSocket upgrade)
   +---> /*      --> [Nginx + React SPA] :80 (static assets)
   |
   +---> [Redis] :6379 (local, bound to 127.0.0.1)
   |
   +---> [Supabase Managed PostgreSQL] (external, connection pooler)
         + Auth (JWT verification)
```

## Prerequisites — What You Need Before Starting

| Item | How to Get It | Cost |
|------|---------------|------|
| **Domain name** | Buy from Namecheap/Cloudflare/Google Domains (e.g., `realestate-agentic.com`) | ~$10/yr |
| **VPS** | DigitalOcean Droplet ($12/mo 2GB RAM) or Hetzner CX22 ($4.50/mo) or AWS Lightsail ($5/mo) | $5-12/mo |
| **Supabase project** | Create at supabase.com (free tier: 500MB DB, 50K MAU auth) | Free |
| **ANTHROPIC_API_KEY** | Already have it | Pay-per-use |
| **GitHub repo** | Already have it | Free |

### Recommended VPS Specs (Minimum)

- **OS:** Ubuntu 24.04 LTS
- **RAM:** 2 GB (4 GB preferred)
- **CPU:** 2 vCPU
- **Disk:** 40 GB SSD
- **Network:** Static IPv4

---

## Task 1: Set Up Supabase Project (DB + Auth)

**Files:** None (external service setup)

- [ ] **Step 1: Create Supabase project**

  Go to https://supabase.com/dashboard -> New Project
  - Project name: `realestate-agentic`
  - Region: Northeast Asia (Tokyo) `ap-northeast-1`
  - Set a strong database password (save it)

- [ ] **Step 2: Collect connection details**

  From Supabase Dashboard -> Settings -> Database:
  ```
  Host: db.<project-ref>.supabase.co
  Port: 5432 (direct) or 6543 (connection pooler — use this)
  Database: postgres
  User: postgres.<project-ref>
  Password: <your-db-password>
  ```

  Connection string for `.env`:
  ```
  DATABASE_URL=postgresql+asyncpg://postgres.<project-ref>:<password>@<host>:6543/postgres
  ```

- [ ] **Step 3: Collect auth keys**

  From Supabase Dashboard -> Settings -> API:
  ```
  SUPABASE_URL=https://<project-ref>.supabase.co
  SUPABASE_ANON_KEY=eyJ... (the anon/public key)
  SUPABASE_SERVICE_ROLE_KEY=eyJ... (the service_role key — keep secret)
  SUPABASE_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1
  SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
  ```

- [ ] **Step 4: Run Alembic migrations against Supabase**

  From your local machine (temporarily set DATABASE_URL to Supabase):
  ```bash
  DATABASE_URL="postgresql+asyncpg://postgres.<ref>:<pw>@db.<ref>.supabase.co:5432/postgres" \
    alembic upgrade head
  ```

- [ ] **Step 5: Create initial dev user**

  ```bash
  DATABASE_URL="..." SUPABASE_URL="..." SUPABASE_SERVICE_ROLE_KEY="..." \
    python scripts/create_dev_user.py
  ```

---

## Task 2: Provision VPS and Install Docker

**Files:** None (server setup)

- [ ] **Step 1: Create VPS**

  DigitalOcean example:
  ```bash
  doctl compute droplet create realestate-prod \
    --region sgp1 \
    --size s-2vcpu-2gb \
    --image ubuntu-24-04-x64 \
    --ssh-keys <your-ssh-key-id>
  ```

- [ ] **Step 2: Secure the server**

  ```bash
  ssh root@<server-ip>

  # Update system
  apt update && apt upgrade -y

  # Create deploy user
  adduser deploy
  usermod -aG sudo deploy

  # Copy SSH key
  mkdir -p /home/deploy/.ssh
  cp ~/.ssh/authorized_keys /home/deploy/.ssh/
  chown -R deploy:deploy /home/deploy/.ssh

  # Disable root SSH login
  sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
  systemctl restart sshd

  # Firewall
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw enable
  ```

- [ ] **Step 3: Install Docker**

  ```bash
  ssh deploy@<server-ip>

  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker deploy
  newgrp docker

  sudo apt install -y docker-compose-plugin

  docker --version
  docker compose version
  ```

---

## Task 3: Create Production Docker Compose with Caddy

**Files:**
- Create: `docker-compose.deploy.yml`
- Create: `Caddyfile`

- [ ] **Step 1: Create Caddyfile**

  ```
  {$DOMAIN:localhost} {
      handle /api/* {
          reverse_proxy app:8000
      }

      handle /ws/* {
          reverse_proxy app:8000
      }

      handle /health {
          reverse_proxy app:8000
      }

      handle /metrics {
          reverse_proxy app:8000
      }

      handle {
          reverse_proxy frontend:80
      }

      header {
          X-Content-Type-Options nosniff
          X-Frame-Options DENY
          Referrer-Policy strict-origin-when-cross-origin
          Permissions-Policy "camera=(), microphone=(), geolocation=()"
          -Server
      }

      log {
          output stdout
          format json
      }
  }
  ```

- [ ] **Step 2: Create docker-compose.deploy.yml**

  ```yaml
  # Production deployment — self-contained with Caddy for HTTPS
  #
  # Usage:
  #   cp .env.production .env
  #   docker compose -f docker-compose.deploy.yml up -d --build

  services:
    caddy:
      image: caddy:2-alpine
      ports:
        - "80:80"
        - "443:443"
        - "443:443/udp"
      volumes:
        - ./Caddyfile:/etc/caddy/Caddyfile:ro
        - caddy_data:/data
        - caddy_config:/config
      environment:
        - DOMAIN=${DOMAIN:-localhost}
      depends_on:
        app:
          condition: service_healthy
        frontend:
          condition: service_started
      restart: unless-stopped
      networks:
        - prod

    app:
      build:
        context: .
        dockerfile: Dockerfile
      command:
        - gunicorn
        - main:app
        - --worker-class=uvicorn.workers.UvicornWorker
        - --workers=4
        - --bind=0.0.0.0:8000
        - --timeout=120
        - --access-logfile=-
      env_file: .env
      environment:
        - ENVIRONMENT=production
      healthcheck:
        test: ["CMD", "python", "-c",
               "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
        interval: 30s
        timeout: 5s
        retries: 3
        start_period: 15s
      deploy:
        resources:
          limits:
            memory: 2G
          reservations:
            memory: 512M
      restart: unless-stopped
      networks:
        - prod

    frontend:
      build:
        context: ./frontend
        dockerfile: Dockerfile
        target: prod
        args:
          - VITE_SUPABASE_URL=${SUPABASE_URL}
          - VITE_SUPABASE_PUBLISHABLE_KEY=${SUPABASE_ANON_KEY}
          - VITE_API_BASE_URL=/api
          - VITE_WS_URL=/ws
      deploy:
        resources:
          limits:
            memory: 128M
      restart: unless-stopped
      networks:
        - prod

    redis:
      image: redis:7-alpine
      command: redis-server --requirepass ${REDIS_PASSWORD:-changeme} --maxmemory 256mb --maxmemory-policy allkeys-lru
      volumes:
        - redis_data:/data
      deploy:
        resources:
          limits:
            memory: 300M
      restart: unless-stopped
      networks:
        - prod

  volumes:
    caddy_data:
    caddy_config:
    redis_data:

  networks:
    prod:
      driver: bridge
  ```

- [ ] **Step 3: Commit both files**

---

## Task 4: Create Production Environment File Template

**Files:**
- Create: `.env.production.example`

- [ ] **Step 1: Create .env.production.example**

  ```bash
  # ── Domain ──
  DOMAIN=your-domain.com

  # ── Anthropic ──
  ANTHROPIC_API_KEY=sk-ant-...

  # ── Database (Supabase connection pooler) ──
  DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<password>@<host>:6543/postgres

  # ── Redis (local container, password-protected) ──
  REDIS_URL=redis://:your-redis-password@redis:6379/0
  REDIS_PASSWORD=generate-a-strong-password-here

  # ── Supabase Auth ──
  SUPABASE_URL=https://<project-ref>.supabase.co
  SUPABASE_ANON_KEY=eyJ...
  SUPABASE_SERVICE_ROLE_KEY=eyJ...
  SUPABASE_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1
  SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
  SUPABASE_JWT_AUDIENCE=authenticated

  # ── Frontend (baked into Vite build) ──
  VITE_SUPABASE_URL=https://<project-ref>.supabase.co
  VITE_SUPABASE_PUBLISHABLE_KEY=eyJ...
  VITE_API_BASE_URL=/api
  VITE_WS_URL=/ws

  # ── App Settings ──
  ENVIRONMENT=production
  LOG_LEVEL=WARNING
  MIROFISH_MODE=mock
  MARKET_DATA_PROVIDER=mock

  # ── Japan Data (optional — mock mode works without these) ──
  REINFOLIB_API_KEY=
  ESTAT_APP_ID=
  RESAS_API_KEY=
  GOOGLE_MAPS_API_KEY=

  # ── CORS (your domain) ──
  CORS_ALLOWED_ORIGINS=https://your-domain.com
  ```

---

## Task 5: Create GitHub Actions CI/CD Pipeline

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create CI workflow**

  `.github/workflows/ci.yml` — runs tests on push to main and tier1/* branches, builds frontend.

- [ ] **Step 2: Create deploy workflow**

  `.github/workflows/deploy.yml` — on push to main, SSH into VPS, git pull, rebuild containers, run migrations.

- [ ] **Step 3: Set GitHub Secrets**

  In repo -> Settings -> Secrets -> Actions:
  ```
  DEPLOY_HOST       = <your-vps-ip>
  DEPLOY_SSH_KEY    = <deploy user private key>
  ```

---

## Task 6: Update CORS and Frontend Build Args

**Files:**
- Modify: `main.py` — use `settings.cors_allowed_origins_list` instead of hardcoded localhost
- Modify: `frontend/Dockerfile` — accept ARG for Vite env vars in build stage

---

## Task 7: First Deploy to VPS

- [ ] Point domain DNS A record to VPS IP
- [ ] Clone repo on VPS: `git clone ... ~/realestate-agentic`
- [ ] Create `.env` from template, fill in real values
- [ ] Build and start: `docker compose -f docker-compose.deploy.yml up -d --build`
- [ ] Run migrations: `docker compose exec app alembic upgrade head`
- [ ] Seed data: `docker compose exec app python scripts/seed_tokyo.py`
- [ ] Verify: `curl https://your-domain.com/health`

---

## Task 8: Backups and Monitoring

- [ ] Create `scripts/backup-db.sh` for daily Supabase pg_dump
- [ ] Schedule via cron: `0 3 * * *`
- [ ] Set up health check cron every 5 minutes
- [ ] Optional: Uptime monitoring via UptimeRobot (free, 5-min checks)

---

## Security Checklist

- [ ] `.env` in `.gitignore` and `.dockerignore` (already done)
- [ ] No secrets in source code
- [ ] Supabase RLS enabled on all tables
- [ ] CORS restricted to your domain only
- [ ] Rate limiting middleware active
- [ ] SSH key-only auth (password login disabled)
- [ ] UFW firewall: only 22, 80, 443
- [ ] Redis internal-only (not exposed to internet)
- [ ] `SUPABASE_SERVICE_ROLE_KEY` only in `.env`, never in frontend

---

## Cost Summary (Monthly)

| Service | Provider | Cost |
|---------|----------|------|
| VPS (2GB) | DigitalOcean/Hetzner | $5-12 |
| Domain | Any registrar | ~$1 |
| Database | Supabase Free Tier | $0 |
| Auth | Supabase Free Tier | $0 |
| HTTPS | Caddy + Let's Encrypt | $0 |
| Claude API | Anthropic (pay-per-use) | ~$5-20 |
| **Total** | | **~$11-33/mo** |

---

## Upgrade Path

1. **More traffic:** Scale gunicorn workers (4 to 8), upgrade VPS to 4GB RAM
2. **Database limits:** Upgrade Supabase to Pro ($25/mo, 8GB, daily backups)
3. **Global users:** Add Cloudflare CDN in front of Caddy
4. **High availability:** Move to Docker Swarm or Kubernetes on 2+ nodes
5. **Managed everything:** Migrate to Railway/Fly.io/Render (~$25/mo)
