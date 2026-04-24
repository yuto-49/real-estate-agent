# Tokyo Release — Implementation Journal (2026-04-14)

Working log for the Tokyo localization + RAG initiative. Captures the approach
per phase, the decisions we took, and the concrete frictions we hit (or expect
to hit) so future-us doesn't re-discover them.

---

## Phase 0 — Local fixture corpus ✅ done today

### Approach

1. Refused to touch production code until a frozen dataset existed. Without
   deterministic fixtures, every test written in Phase 1+ would either depend
   on live APIs (flaky, costs money, leaks PII under APPI) or on whatever data
   happened to be in a dev's laptop that morning.
2. Modeled the fixture tree to mirror the *real* source layout we will later
   replace with live data: one subdirectory per upstream source, schemas that
   match the published field names (`bukken_bangou`, `shozaichi`,
   `rinshii_eki`, ...) so loaders don't need to be rewritten when we swap the
   mock provider for REINS/reinfolib.
3. Hand-authored 9 REINS-style listings across 3 wards (港区 / 世田谷区 / 新宿区)
   chosen for their regulatory variety: 商業地域 + 新耐震 (Minato central),
   第一種低層住居専用 + 旧耐震 (Setagaya), and 近隣商業 with 旧耐震 reformed
   (Shinjuku 神楽坂). This diversity matters for Phase 2's `guardrails_jp`
   tests.
4. Kept the per-source fixture count *deliberately tiny* (9 listings, 13 MLIT
   rows, 4 e-Stat records). The MVP of every loader needs to work on this set
   in < 1s. Bulk dev data goes through `scripts/fetch_tokyo_dev_data.py`
   (future) so it never enters the test loop.

### Artifacts created

| Path | Purpose |
|---|---|
| `tests/fixtures/tokyo/README.md` | Provenance + license table + do-not-commit rules for 重要事項説明書 PDFs |
| `tests/fixtures/tokyo/.gitignore` | Excludes PDF drops under `juuyou_docs/` while keeping `.gitkeep` |
| `tests/fixtures/tokyo/reins_samples/listings_{minato,setagaya,shinjuku}.json` | 9 synthetic listings matching the `reins-baibai-bukken-v1` shape |
| `tests/fixtures/tokyo/mlit_transactions/2024_tokyo_13_sample.csv` | 13 rows in reinfolib 取引価格情報 CSV format |
| `tests/fixtures/tokyo/estat_demographics/chome_population.json` | 4 町丁目 population records |
| `tests/fixtures/tokyo/hazard_maps/minato_flood.geojson` | 2 hazard polygons (洪水 + 津波) |
| `tests/fixtures/tokyo/zoning/tokyo23_zoning_sample.geojson` | 3 用途地域 features across the sample wards |
| `tests/fixtures/tokyo/addresses/tokyo23_normalized.json` | 6 raw → normalized address pairs |
| `scripts/seed_tokyo.py` | Idempotent Postgres loader consuming the fixture tree |

### Errors and frictions encountered

**1. Model shape mismatch — US fields vs JP fields.**

The current `Property` model still has `hoa_fees: Float`, `sqft: Integer`,
`asking_price: Float`. It has no `address_jp`, `nearest_stations`, `built_year`,
`structure`, `youto_chiiki`, or JPY-precision money columns. We have not yet
run the Phase 1 migration, so Phase 0 must seed into the legacy schema.

> Mitigation: stashed all JP fields in the existing `neighborhood_data.jp`
> JSONB subkey and `disclosures.*`. `scripts/seed_tokyo.py` is now the
> canonical list of call sites that must be updated when Phase 1 migration
> adds first-class JP columns. Grep `neighborhood_data["jp"]` to audit.

**2. JPY precision silently lost through `Float`.**

`Float` cannot represent every integer yen past `2^24 ≈ 16,777,216`. Listings
like 港区 六本木 @ ¥198,000,000 serialize fine by luck, but once we ingest MLIT
rows with 億円 values the bit pattern no longer round-trips. The DB accepts
the write and the bug is invisible until reconciliation.

> Mitigation, noted for Phase 1: migrate all money columns to
> `Numeric(15, 0)`. Added a prominent docstring in `seed_tokyo.py` flagging
> this as the #1 call site to fix.

**3. Legacy US guardrail `REQUIRED_DISCLOSURES` blocks JP listings.**

`agent/guardrails.py` enforces `known_defects`, `flood_zone`, `hoa_fees`,
`lead_paint`, `environmental_hazards`. Seeding JP listings without those keys
makes the seller flow trip the `validate_disclosures` guard the moment any
test touches it.

> Mitigation: synthesize the US disclosure keys from JP data in the seed
> loader (flood_zone=`unknown`, lead_paint=`na`, etc.) and record the real JP
> disclosure in `disclosures.*_jp` keys. This is a deliberate temporary hack
> — Phase 2 will replace `REQUIRED_DISCLOSURES` with `REQUIRED_JUUYOU_JIKOU`
> behind a `settings.jurisdiction` switch.

**4. No natural key on `Property` for idempotency.**

The model has no `external_ref` column, so re-running the seeder would
duplicate listings every time. The existing `seed_properties.py` script does
not handle re-runs either.

> Mitigation: Store `bukken_bangou` in `disclosures.reins_bukken_bangou`, query
> existing values on startup, skip any listing whose REINS ref already exists.
> This is O(N) in listing count — acceptable for fixtures; must be an index
> (or dedicated `external_ref` column) before production.

**5. REINS redistribution risk.**

Even authoring realistic-looking listings carries risk: if someone later
drops a *real* REINS record into `reins_samples/`, the repo becomes a
redistribution of licensed data.

> Mitigation: loud "synthetic" markers in every JSON (`fixture_source`,
> `SYN-13xxx-*` IDs, README callout, `.gitignore` for PDFs). Add a CI lint
> rule (future) that rejects any PR changing these files unless the commit
> message contains `synthetic-ok`.

**6. Mojibake risk reading CSVs.**

Japanese CSV encoding in the wild is a zoo (Shift_JIS, CP932, UTF-8 w/ BOM).
reinfolib's downloads default to UTF-8, but REINS exports are historically
CP932.

> Mitigation: our fixture is pure UTF-8 (no BOM). The loader in Phase 3 must
> detect encoding per file (`charset-normalizer`), not assume. Noted for
> Phase 3 design.

### Verification

```
$ python -c "from scripts.seed_tokyo import _load_reins_files, _reins_to_property_kwargs; \
             from pathlib import Path; \
             ls = _load_reins_files(Path('tests/fixtures/tokyo/reins_samples')); \
             [_reins_to_property_kwargs(x) for x in ls]; \
             print(len(ls))"
9
```

Parsing passes; no DB write attempted (Postgres not running locally at the
time of writing this journal — that is itself a Phase 0 gap to close before
the integration tier lands).

### Next step

Before moving to Phase 1, add an `scripts/seed_tokyo.py` smoke test under
`tests/test_seed_tokyo.py` that runs the parser only (no DB) so CI catches
fixture drift.

---

## Credentials and downloads — cross-phase checklist

Single source of truth for "what do I need to sign up for?". Organized by
phase. Every credential should land in `.env` (or a secret manager in prod),
*never* inline in code or committed fixtures.

### Phase 0 — fixtures

Nothing. All files are authored or derived from public schemas.

### Phase 1 — domain model localization

| Item | Source | How to obtain | Env var |
|---|---|---|---|
| Geolonia address tables | https://github.com/geolonia/japanese-addresses | `pip install japanese-addresses` or vendor the JSON under `services/providers_jp/geolonia/data/` | none (local) |
| Python `pendulum` or `zoneinfo` | stdlib | `tzdata` package on Windows only | none |

No network credentials yet.

### Phase 2 — guardrails_jp

| Item | Source | How to obtain | Env var |
|---|---|---|---|
| 重要事項説明書ひな形 PDF | 国土交通省 宅建業法 section (search "重要事項説明書 ひな形") | Download manually, save to `tests/fixtures/tokyo/juuyou_docs/jukensetsumei_template.pdf` (git-ignored) | none |
| 宅建業法報酬告示 text | 国土交通省告示 (検索: "宅地建物取引業者が受けることのできる報酬の額") | Copy the tiered fee table into `agent/guardrails_jp.py` as a constant | none |

No API keys.

### Phase 3 — data ingestion adapters

| Service | Purpose | How to obtain | Env var |
|---|---|---|---|
| **MLIT 不動産情報ライブラリ API** | 取引価格情報 + 地価公示 | Register at `https://www.reinfolib.mlit.go.jp/` developer portal → issue API key. Free. | `REINFOLIB_API_KEY` |
| **e-Stat API** | 国勢調査 + 家計調査 + 社会人口統計 | Register at `https://www.e-stat.go.jp/api/` → 利用登録 → receive アプリケーションID. Free. | `ESTAT_APP_ID` |
| **RESAS API** | 地域経済 (人口流動, 事業所) | Register at `https://opendata.resas-portal.go.jp/` → receive API key. Free. | `RESAS_API_KEY` |
| **国土数値情報** downloads | 用途地域 / ハザード / 学区 GeoJSON | `https://nlftp.mlit.go.jp/ksj/` → agree to 利用約款 → download ZIPs per prefecture. No key. | none |
| **ハザードマップポータル** | 重ね合わせハザード (洪水/津波/土砂/高潮/液状化) | `https://disaportal.gsi.go.jp/` → ベクトルタイル, WMS endpoints. No key. | none |
| **Geolonia community-geocoder** | 住所 → lat/lng (offline capable) | `https://github.com/geolonia/community-geocoder` — vendor offline, or call the free hosted endpoint | `GEOLONIA_API_KEY` (optional, for hosted) |
| **Google Maps Platform (JP)** | Production-quality geocoding + Places | GCP console → Maps Platform → enable Geocoding/Places API → create key, restrict by referrer + API | `GOOGLE_MAPS_API_KEY` |
| **Yahoo! Japan 地図 API** | JP-optimized geocoding alternative | https://developer.yahoo.co.jp/ → アプリケーション登録 → Client ID | `YAHOO_JP_CLIENT_ID` |
| **REINS (live)** | Primary listings (when we have a 宅建業者 license) | Requires 宅建業免許 + 不動産流通機構 (東日本/中部/近畿/西日本) membership. Each member gets REINS IP Type接続 credentials. Not self-serve. | `REINS_MEMBER_ID`, `REINS_PASSWORD`, `REINS_CLIENT_CERT_PATH` |
| **登記情報提供サービス** | 登記簿謄本 取得 | Register at `https://www1.touki.or.jp/gateway.html` (法務省外郭) → 個人 or 法人登録 → ID + PW (per-query fee) | `TOUKI_USER_ID`, `TOUKI_PASSWORD` |

### Phase 4 — pgvector + RAG

| Service | Purpose | How to obtain | Env var |
|---|---|---|---|
| **PostgreSQL 16 + pgvector extension** | Vector store | Local: `docker compose up postgres` then `CREATE EXTENSION vector`. Prod: Aurora PostgreSQL (Tokyo) enables pgvector via parameter group. | already in `DATABASE_URL` |
| **pgroonga extension** (optional) | Japanese BM25 (Mroonga tokenizer) | `apt install postgresql-16-pgdg-pgroonga` locally; AWS RDS supports via extension add. | none |
| **Voyage AI embeddings** | Production multilingual embeddings (paired with Claude) | Sign up at `https://dash.voyageai.com/` → API key. Free tier exists. | `VOYAGE_API_KEY` |
| **Cohere embeddings/rerank (alt)** | Multilingual embed + rerank | `https://dashboard.cohere.com/` → API key. | `COHERE_API_KEY` |
| **Sentence-Transformers multilingual model** | Offline / CI embeddings | `pip install sentence-transformers` then `SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')`. ~1GB cached to `~/.cache/huggingface/`. | none |
| **LlamaParse** (optional) | PDF → structured markdown for 重説/契約書 | `https://cloud.llamaindex.ai/` → API key. Free tier 1k pages/day. | `LLAMA_CLOUD_API_KEY` |
| **unstructured.io** (alt) | Self-hostable PDF chunker | `pip install "unstructured[local-inference]"`. Optional hosted key. | `UNSTRUCTURED_API_KEY` |
| **AWS Textract** (optional) | OCR for scanned 登記簿 / 重説 | AWS IAM user w/ `AmazonTextractFullAccess`, Tokyo region (`ap-northeast-1`) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=ap-northeast-1` |

### Phase 5 — offline embedder / local testing

| Item | Source | How to obtain | Env var |
|---|---|---|---|
| `sentence-transformers` model weights | HuggingFace | First run downloads `paraphrase-multilingual-mpnet-base-v2` (~1GB) to `~/.cache/huggingface/`. Commit the hash of the model in `pyproject.toml` dependencies. | `HF_HOME` (optional, to relocate cache) |
| Sudachi Japanese tokenizer dictionary | SudachiPy | `pip install sudachipy sudachidict_core`. `sudachidict_full` is 1GB+; `sudachidict_core` (~50MB) is enough for chunking. | none |
| `pytest-postgresql` + Postgres binary | pip + local Postgres | `pip install pytest-postgresql` plus the `postgres` binary on PATH (Docker container is fine — mount its `pg_ctl`). | `POSTGRES_BINARY_PATH` if non-standard |

### Phase 6 — local integration tests

No new credentials. Runs entirely against fixtures + `pytest-postgresql` +
DeterministicHashEmbedder / LocalSTEmbedder.

### Phase 7 — production rollout (Tokyo)

| Service | Purpose | Env var |
|---|---|---|
| **AWS account with Tokyo region** | Hosting, APPI residency | `AWS_REGION=ap-northeast-1` |
| **Amazon Bedrock (Tokyo)** | Claude via JP region for APPI residency | `BEDROCK_MODEL_ID=anthropic.claude-opus-4-6-v1:0`, `BEDROCK_REGION=ap-northeast-1` |
| **AWS Secrets Manager** | Central secret store | `AWS_SECRETS_ARN_PREFIX` |
| **AWS KMS** | Encrypt at rest (CMK in ap-northeast-1) | `KMS_KEY_ID` |
| **Aurora PostgreSQL (Tokyo) + pgvector** | Primary DB | `DATABASE_URL` |
| **ElastiCache Redis (Tokyo)** | Cache/pub-sub | `REDIS_URL` |
| **SQS (Tokyo)** | Durable queue for REINS ingestion + rerank | `SQS_INGEST_QUEUE_URL`, `SQS_DLQ_URL` |
| **S3 (Tokyo, Object Lock)** | Document archive for 重説/契約書 | `S3_DOCUMENT_BUCKET` |
| **CloudFront + ACM cert** | HTTPS frontend | `CDN_DISTRIBUTION_ID` |
| **Route 53 + custom domain** | | `APP_DOMAIN` |
| **Datadog / New Relic (JP)** or **Grafana Cloud AP region** | Observability (OTel-compatible) | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` |
| **Sentry** (optional) | Error tracking | `SENTRY_DSN` |

### Documents to download locally (one-time, per developer)

All of these belong under `tests/fixtures/tokyo/juuyou_docs/` or
`scripts/downloads/` (git-ignored) — never committed:

1. **重要事項説明書ひな形 (PDF)** from 国土交通省 宅建業法 section — template only.
2. **不動産売買契約書ひな形 (PDF)** from the same source — template only.
3. **MLIT 取引価格情報 CSV (2022–2024, 13=東京都 filter)** from reinfolib — bulk
   historical comps for dev DB (~80MB).
4. **国土数値情報 A29 用途地域 東京都 GeoJSON** (zoning polygons).
5. **国土数値情報 A31 洪水浸水想定区域 東京都 GeoJSON**.
6. **国土数値情報 A32 津波浸水想定 GeoJSON** (coastal wards only).
7. **国土数値情報 A33 土砂災害警戒区域 GeoJSON**.
8. **e-Stat 国勢調査 2020 小地域 東京都 CSV** (町丁目 population/households).
9. **e-Stat 住宅・土地統計調査 2018 CSV** (owner vs renter, 空き家率).
10. **国税庁 路線価図 (任意)** — for land valuation cross-checks.
11. **Geolonia 住所データ** (`japanese-addresses` package) — already `pip`-able,
    no download step needed.

Each source has a 利用約款 — read before redistributing. 国土数値情報 in
particular prohibits some commercial redistribution patterns.

---

## Open questions for Phase 1

- Do we keep the US code path alive in the same codebase (jurisdiction flag)
  or fork? Current plan: flag-based, because a fork doubles the maintenance
  surface and we want the Tokyo path to eat the US path eventually.
- Where do we store user 宅建 license info? — likely a new `broker_profiles`
  table (免許番号, 免許権者, 有効期間, 専任取引士).
- Do we need per-tenant sharding now, or defer? Defer — Tokyo MVP is
  single-tenant; per-tenant comes when we onboard a second agency.
