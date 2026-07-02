# Production Scaling Plan: From Dev to Business

**Opinionated infrastructure plan for running Real Estate Agentic as a paid SaaS product.**

---

## Current State (Dev)

```
Windows 11 laptop
  └── Docker Compose (dev mode)
       ├── FastAPI (uvicorn, 1 worker)
       ├── React (Vite dev server)
       ├── PostgreSQL 16 (shared container)
       └── Redis 7 (shared container)

External:
  ├── Supabase (auth, free tier)
  ├── Claude API (Anthropic, pay-per-call)
  └── TomTom Maps (geocoding)
```

**Problems to solve for production:**
- No HTTPS, no domain, no CDN
- Single process, no horizontal scaling
- No backups, no monitoring, no alerting
- No CI/CD pipeline
- No secret management (`.env` file on disk)
- Scout worker has nowhere to run persistently
- PDF generation (WeasyPrint) needs system libraries

---

## My Recommendation: Start Simple, Scale When Revenue Demands

**Opinion:** Do NOT over-engineer infrastructure before you have paying users. The platform's unit economics ($0.012/analysis, $62/month OpEx at 1K analyses) mean you can run profitably on a single $50/month server. Scale complexity only when traffic or revenue justifies it.

### Phase 1: First 50 Users (Month 1-3)

**One VPS. That's it.**

```
Hetzner / Vultr / Conoha VPS (Japan DC)
  Ubuntu 24.04 LTS, 4 vCPU, 8GB RAM, 160GB NVMe
  ~$30-40/month (Hetzner CPX31 or Conoha equivalent)

  ┌─────────────────────────────────────────────┐
  │  Docker Compose (prod override)              │
  │                                              │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
  │  │ Caddy    │  │ FastAPI  │  │ Frontend │  │
  │  │ (reverse │→ │ gunicorn │  │ (nginx)  │  │
  │  │  proxy + │  │ 4 workers│  │ static   │  │
  │  │  auto-TLS│  └──────────┘  └──────────┘  │
  │  └──────────┘                               │
  │  ┌──────────┐  ┌──────────┐                 │
  │  │ Postgres │  │ Redis    │                 │
  │  │ 16       │  │ 7        │                 │
  │  └──────────┘  └──────────┘                 │
  │  ┌──────────────────────────┐               │
  │  │ Scout Worker (cron/APSch)│               │
  │  └──────────────────────────┘               │
  └─────────────────────────────────────────────┘

External:
  ├── Supabase (auth, free → Pro at $25/mo when needed)
  ├── Claude API (Anthropic)
  ├── Resend or SendGrid (email, free tier)
  └── Cloudflare (DNS + CDN, free tier)
```

**Why this setup:**
- **Hetzner or Conoha** — cheapest reliable VPS with Japan datacenter. Latency matters because your users are in Tokyo. Conoha (GMO) has Tokyo/Osaka DCs. Hetzner has no Japan DC but has good Singapore routing.
- **Caddy** over nginx as reverse proxy — automatic HTTPS via Let's Encrypt, zero config. You already have nginx for the frontend static files, Caddy sits in front of everything.
- **Gunicorn + 4 UvicornWorkers** — your `docker-compose.prod.yml` already has this. 4 workers on 4 vCPU handles ~200 concurrent requests.
- **No managed database yet** — Postgres in Docker with daily `pg_dump` to object storage is fine for 50 users. You don't need Supabase DB or RDS.

**Monthly cost:**

| Service | Cost |
|---------|------|
| VPS (4 vCPU, 8GB) | $35 |
| Supabase Auth (free tier) | $0 |
| Claude API (~2K analyses/month) | $24 |
| Cloudflare (DNS + CDN) | $0 |
| Resend email (100 emails/day free) | $0 |
| Domain (.jp or .com) | ~$1.50 |
| Object storage backup (Hetzner/B2) | $2 |
| **Total** | **~$63/month** |

**Break-even:** 2 users at $50/month or 1 user at $100/month.

---

### Phase 2: 50-500 Users (Month 3-9)

**Split database out. Add monitoring. Automate deployment.**

```
┌─────────────────────────────────────────────┐
│  VPS 1: Application (same as Phase 1)       │
│  ┌──────┐ ┌──────────┐ ┌──────┐            │
│  │Caddy │ │ FastAPI  │ │nginx │            │
│  │      │ │ 4 worker │ │static│            │
│  └──────┘ └──────────┘ └──────┘            │
│  ┌──────────────────────────┐               │
│  │ Scout Worker + APScheduler│              │
│  └──────────────────────────┘               │
│  ┌──────┐                                   │
│  │Redis │ (still local — low latency)       │
│  └──────┘                                   │
└─────────────────────────────────────────────┘
         |
         | Private network
         v
┌─────────────────────────────────────────────┐
│  Managed PostgreSQL                          │
│  (Supabase Pro / Neon / Hetzner managed)     │
│  - Automatic backups                         │
│  - Point-in-time recovery                    │
│  - Connection pooling (PgBouncer)            │
└─────────────────────────────────────────────┘

New additions:
  ├── GitHub Actions CI/CD (free for public repo)
  ├── Grafana Cloud (free tier: 10K metrics)
  ├── Sentry (error tracking, free tier)
  └── Uptime Robot (monitoring, free tier)
```

**Key changes:**
- **Managed PostgreSQL** — the biggest reliability upgrade. Automatic backups, failover, and you stop worrying about data loss. Neon (serverless Postgres) is the cheapest option and you already have the MCP tool for it.
- **CI/CD** — GitHub Actions: lint + test on PR, deploy on merge to main. `ssh` + `docker compose pull && docker compose up -d` is enough.
- **Monitoring** — Grafana Cloud free tier gives you metrics. Sentry catches Python exceptions. Uptime Robot pings your health endpoint.

**Monthly cost:**

| Service | Cost |
|---------|------|
| VPS (same) | $35 |
| Managed Postgres (Neon Pro / Supabase Pro) | $25 |
| Supabase Auth (Pro) | $25 |
| Claude API (~10K analyses) | $120 |
| Sentry (free tier) | $0 |
| Grafana Cloud (free tier) | $0 |
| Resend (Pro if needed) | $20 |
| Cloudflare | $0 |
| **Total** | **~$225/month** |

**Break-even:** 5 users at $50/month.

---

### Phase 3: 500-5,000 Users (Month 9-18)

**This is where architecture actually changes.**

```
┌──────────────────────────────────────────────────────────┐
│                    Cloudflare (CDN + WAF)                 │
└──────────────┬───────────────────────────────────────────┘
               |
┌──────────────▼───────────────────────────────────────────┐
│  Load Balancer (Hetzner LB / Caddy on dedicated VPS)     │
└──────────┬───────────────────┬───────────────────────────┘
           |                   |
┌──────────▼─────┐  ┌─────────▼──────┐
│  App Server 1  │  │  App Server 2  │    (horizontal scale)
│  FastAPI       │  │  FastAPI       │
│  4 workers     │  │  4 workers     │
└──────────┬─────┘  └─────────┬──────┘
           |                   |
┌──────────▼───────────────────▼──────┐
│  Redis (managed — Upstash or        │
│  Hetzner managed)                    │
│  - Session store                     │
│  - Scout job queue (Redis Streams)   │
│  - Rate limiting                     │
└──────────┬──────────────────────────┘
           |
┌──────────▼──────────────────────────┐
│  PostgreSQL (managed, read replica)  │
│  - Primary: writes                   │
│  - Replica: read-heavy queries       │
│  - Connection pooler (PgBouncer)     │
└──────────────────────────────────────┘

Separate worker processes:
┌──────────────────────────────────────┐
│  Worker VPS                          │
│  ┌──────────────────────────┐        │
│  │ Scout Worker (persistent)│        │
│  │ PDF Generator            │        │
│  │ Analyst Council fan-out  │        │
│  └──────────────────────────┘        │
└──────────────────────────────────────┘

New additions:
  ├── Object storage (S3-compatible) for PDFs + report cache
  ├── Proper secrets management (Vault or cloud provider)
  ├── Log aggregation (Loki or Datadog)
  └── Staging environment (clone of prod)
```

**Monthly cost: ~$500-800/month** (profitable at 15+ users at $50/month)

---

## Technology Dependency Matrix

### Required (Day 1)

| Dependency | What | Why | Alternatives |
|-----------|------|-----|-------------|
| **Ubuntu 24.04 LTS** | Server OS | Industry standard, best Docker support, widest package availability | Debian 12 (equally good, more conservative) |
| **Docker + Compose** | Containerization | You already have it working. Reproducible deploys | Podman (drop-in replacement, rootless by default) |
| **PostgreSQL 16** | Primary database | Already in use, async support via asyncpg, JSONB for flexible schemas | None — do not switch. Your models, migrations, and queries are Postgres-specific |
| **Redis 7** | Cache + queue | Already in use for geocache, rate limiting. Scout worker needs it as job queue | Valkey (Redis fork, API-compatible, truly open source) |
| **Python 3.11+** | Runtime | Already locked in. Type hints, asyncio, dataclasses | 3.12/3.13 when convenient (no urgency) |
| **Node 20 LTS** | Frontend build | For Vite/React build step only. Not a runtime dependency | Node 22 LTS when it ships |

### Required (Before Launch)

| Dependency | What | Why | My Pick |
|-----------|------|-----|---------|
| **Reverse proxy + TLS** | HTTPS termination | Non-negotiable for production. Auto-renewing certificates | **Caddy** — 10 lines of config, auto-HTTPS. Nginx requires more setup and certbot |
| **Domain + DNS** | Public access | Users need a URL | **Cloudflare** (free) — DNS + CDN + DDoS protection + analytics. Register domain on Cloudflare Registrar (cheapest) |
| **Email delivery** | Scout alerts, account verification | Transactional email from your domain | **Resend** — great DX, good free tier (100/day), good deliverability. Alternative: SendGrid |
| **Error tracking** | Catch production crashes | You need to know when things break before users tell you | **Sentry** — Python SDK is excellent, free tier is generous (5K events/month) |
| **Uptime monitoring** | Health checks | Know when the server is down | **Uptime Robot** (free, 5-minute checks) or **Better Stack** (nicer UI, free tier) |

### Required (At Scale / Phase 2+)

| Dependency | What | Why | My Pick |
|-----------|------|-----|---------|
| **Managed Postgres** | Database reliability | Automatic backups, point-in-time recovery, no 3am pages | **Neon** — serverless, branches for staging, cheapest. You already have the MCP tool. Alternative: Supabase DB (bundled with auth) |
| **CI/CD** | Automated deploy | Stop SSH-ing into servers | **GitHub Actions** — free for your repo, simple Docker workflow |
| **Log aggregation** | Debugging production issues | structlog output needs to go somewhere searchable | **Grafana Cloud + Loki** (free tier) or **Better Stack Logs** |
| **Object storage** | PDF reports, backups, static assets | Don't store files on the app server | **Cloudflare R2** — S3-compatible, no egress fees. Alternative: Backblaze B2 |
| **Job queue** | Scout worker, analyst council fan-out, PDF generation | Background jobs need reliable execution | **Redis Streams** (already have Redis) or **arq** (Python async Redis queue). Avoid Celery — overkill for your use case |

### Optional (Nice to Have)

| Dependency | What | Why | When |
|-----------|------|-----|------|
| **Terraform / Pulumi** | Infrastructure as code | Reproducible infra setup | When you have 2+ environments |
| **Kubernetes** | Container orchestration | Auto-scaling, self-healing | **Not until 5,000+ users.** K8s is operational overhead you don't need early. Docker Compose on a VPS is fine for years |
| **APM (Application Performance Monitoring)** | Request tracing | Find slow queries, bottleneck endpoints | When response times matter (Phase 2+). Sentry has basic APM |
| **Feature flags** | Gradual rollout | A/B test features, kill switches | When you ship features to different user tiers. LaunchDarkly or PostHog |
| **WAF (Web Application Firewall)** | Security | Block malicious requests | Cloudflare free tier includes basic WAF. Upgrade to Pro ($20/mo) for custom rules |

---

## Opinions: What NOT to Do

### 1. Do NOT use AWS/GCP/Azure yet

**Why:** Cloud provider bills are unpredictable and expensive at small scale. A $35/month Hetzner VPS gives you more compute than a $100/month EC2 instance. The managed service ecosystem is great but you're paying for complexity you don't need.

**When to switch:** When you need auto-scaling (sustained >500 concurrent users), multi-region, or compliance certifications (SOC2, ISO27001) that your investors or enterprise customers demand.

**If you must use cloud:** Use **Fly.io** or **Railway** — they're the middle ground between VPS and full cloud. Docker-native, reasonable pricing, good DX.

### 2. Do NOT use Kubernetes

**Why:** K8s solves problems you don't have (orchestrating dozens of microservices, auto-scaling across zones). Your app is a monolith with a worker — Docker Compose handles this perfectly. K8s has a massive learning curve and operational burden.

**When to switch:** When you have 5+ services, need auto-scaling based on queue depth, or hire a DevOps engineer.

### 3. Do NOT build microservices

**Why:** Your FastAPI monolith is well-structured (12 routers, clean separation). Splitting into microservices adds network latency, deployment complexity, and distributed debugging nightmares — for zero benefit at your scale.

**What to do instead:** Keep the monolith. Extract the Scout Worker as a separate process (same codebase, different entrypoint) because it has a different lifecycle (cron vs request/response). That's it.

### 4. Do NOT self-host Supabase

**Why:** Supabase hosted gives you auth, JWT verification, user management, and a dashboard for free/$25/month. Self-hosting means managing GoTrue, Kong, PostgREST, and the Supabase Studio — operational burden with no benefit.

### 5. Do NOT use a separate API gateway (Kong, Traefik, etc.)

**Why:** Caddy does reverse proxy + TLS + rate limiting. FastAPI does auth middleware + CORS. You don't need a third layer. API gateways add latency and complexity.

**When to switch:** When you have multiple backend services behind different domains, or need OAuth2 proxy for third-party integrations.

---

## Japan-Specific Infrastructure Considerations

### Data Residency

Japanese investors may care (or regulators may require) that their data stays in Japan.

| Service | Japan-resident option |
|---------|---------------------|
| **VPS** | Conoha (Tokyo/Osaka), Sakura Cloud (Tokyo/Osaka/Ishikari), Vultr (Tokyo) |
| **Managed Postgres** | Neon (AWS ap-northeast-1), Supabase (ap-northeast-1 available) |
| **CDN** | Cloudflare has Tokyo PoP |
| **Object storage** | Cloudflare R2 (APAC), Sakura Object Storage |
| **Email** | Resend routes through closest region |

**My pick for Japan residency:** **Conoha VPS** (Tokyo DC, GMO Internet Group, Japanese company, yen billing) + **Neon on ap-northeast-1** + **Cloudflare**.

### Compliance

| Requirement | How to Meet |
|------------|-------------|
| **個人情報保護法 (Personal Information Protection Act)** | Privacy policy, data handling disclosure, opt-out for marketing. Your domain_events table already provides the audit trail |
| **宅建業法 (Real Estate Transactions Act)** | Your domain_events already log every recommendation with inputs. Add a "this is not financial advice" disclaimer to every report |
| **特定商取引法 (Specified Commercial Transactions Act)** | Required for SaaS: publish company info, pricing, cancellation policy on your website |
| **資金決済法 / 割賦販売法** | If you take credit cards: use Stripe Japan (handles compliance). Do NOT process cards yourself |

### Payment Processing

**Stripe Japan** — the only sane choice for a SaaS in Japan. Supports:
- Credit cards (Visa/Mastercard/JCB/Amex)
- Konbini payment (convenience store payment — important for Japan)
- Bank transfer (振込)
- Invoicing (請求書払い — enterprise customers expect this)

Monthly cost: 3.6% per transaction (standard Japan rate).

---

## Deployment Pipeline

### Minimum Viable CI/CD (Phase 1)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --tb=short

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: deploy
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/realestate-agentic
            git pull origin main
            docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
            docker compose exec app alembic upgrade head
```

**That's it.** No Terraform, no Ansible, no ArgoCD. When this becomes insufficient, then invest in better tooling.

### Backup Strategy (Phase 1)

```bash
# Cron job on VPS, daily at 3:00 AM JST
0 3 * * * docker compose exec -T postgres pg_dump -U dev realestate | \
  gzip | \
  rclone rcat r2:realestate-backups/db/$(date +\%Y-\%m-\%d).sql.gz

# Keep 30 days of daily backups
0 4 * * * rclone delete r2:realestate-backups/db/ --min-age 30d
```

---

## Scaling Decision Tree

```
Q: Is the server CPU consistently >70%?
├── Yes → Add a second app server behind Caddy load balancer ($35/mo)
└── No
    Q: Is the database the bottleneck (slow queries)?
    ├── Yes → Add read replica, optimize queries, add indexes
    └── No
        Q: Are Claude API calls slow (>5s)?
        ├── Yes → Run analyst council on worker process, return results async
        └── No
            Q: Are Scout cycles taking too long?
            ├── Yes → Dedicated worker VPS, parallelize source fetching
            └── No → You're fine. Don't change anything.
```

---

## Cost Projection by User Count

| Users | Claude API | Infra | Total/mo | Revenue (at $80/user) | Margin |
|-------|-----------|-------|----------|----------------------|--------|
| 10 | $24 | $63 | $87 | $800 | 89% |
| 50 | $120 | $100 | $220 | $4,000 | 95% |
| 200 | $480 | $225 | $705 | $16,000 | 96% |
| 500 | $1,200 | $500 | $1,700 | $40,000 | 96% |
| 1,000 | $2,400 | $800 | $3,200 | $80,000 | 96% |

**The margins are excellent.** Claude API is the largest variable cost and it scales linearly. Infrastructure costs grow sub-linearly because you add capacity in steps, not per-user.

---

## Summary: What to Do Right Now

| Priority | Action | Cost | Time |
|----------|--------|------|------|
| 1 | Buy a Conoha VPS (Tokyo, 4vCPU/8GB) | $35/mo | 1 hour |
| 2 | Set up Caddy + Docker Compose prod | $0 | 2 hours |
| 3 | Register domain + Cloudflare DNS | $12/year | 30 min |
| 4 | Set up `pg_dump` backup cron to R2 | $2/mo | 1 hour |
| 5 | GitHub Actions CI/CD (test + deploy) | $0 | 2 hours |
| 6 | Sentry error tracking | $0 | 30 min |
| 7 | Uptime Robot health check | $0 | 15 min |
| 8 | Stripe Japan account | 3.6%/tx | 1-2 days (KYC) |

**Total: ~$40/month + one day of setup work.** Everything else can wait until you have paying users.

---

*Plan generated June 5, 2026. Opinions are based on running SaaS products in the $0-$50K MRR range. Adjust when your situation changes — infrastructure decisions should follow revenue, not precede it.*
