# Market Signal Sources

Catalog of external data sources that can populate the `market_signals`
table. Schema reminder:
`market_signals(signal_type, subject_type, subject_id, value, payload, observed_at, source)`.
The `source` column should record which provider wrote the row.

The integration target is the `MarketSignalProvider` Protocol in
`services/signal_providers/base.py`. Each entry below tells you what's
available, what it costs, and which signal_type it can fill.

---

## Recommended starting set (Chicago / US)

| Provider | Auth | Rate limit | Yields (signal_type) | Subject |
|---|---|---|---|---|
| **Chicago Crimes (SODA)** | none (recommended `$$app_token`) | 1k req/hr without token | `safety_score` | `neighborhood` (zip) |
| **FEMA NFHL** | none | unmetered | `hazard.flood` | `property` (lat/lon) |
| **HUD Fair Market Rent** | free token | unmetered | `median_rent` | `neighborhood` (zip / FIPS) |
| **Census ACS 5-Year** | free key | 500 req/day | `median_sale_price`, `median_rent` | `neighborhood` (zip / tract) |
| **GTFS-feed stop density** | none (CTA, MBTA, etc.) | unmetered | `transit_score` | `neighborhood` (zip) |
| **NCES schools** | none | unmetered | `school_score` | `neighborhood` (district) |
| **Zillow Research CSV** | none (downloads) | weekly cadence | `median_sale_price`, `median_rent`, `inventory_pressure` | `neighborhood` (zip / metro) |
| **Redfin Data Center CSV** | none (downloads) | weekly cadence | `median_sale_price`, `inventory_pressure`, time-on-market | `neighborhood` (zip / metro) |
| **FRED (Federal Reserve)** | free key | unmetered | macro signals (mortgage rate, HPI) | `jurisdiction` |

---

## Detail

### 1. Chicago Crimes — Open Data (Socrata SODA)
- Endpoint: `https://data.cityofchicago.org/resource/ijzp-q8t2.json`
- Filter: `?$where=date > '2024-01-01' AND community_area=...`
- Auth: optional (`X-App-Token` header for higher quota)
- Mapping:
  `safety_score = clamp(10 - (incidents_per_1k_residents / 25 * 10), 0, 10)`
- Subject: zip (need a community-area→zip lookup table; ship a small static map first).
- Upside: free, real-time, well-known data shape.
- Provider: `services/signal_providers/chicago_crime.py` (shipped).

### 2. FEMA National Flood Hazard Layer
- Endpoint: `https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query`
- Auth: none.
- Query: `?geometry={x},{y}&geometryType=esriGeometryPoint&inSR=4326&outFields=FLD_ZONE,SFHA_TF&returnGeometry=false&f=json`
- Mapping: `hazard` payload `{flood_zone: "AE", in_sfha: true}` per property.
- Subject: property (lat/lon).
- Notes: ArcGIS FeatureServer; polygons cover most of the US. Empty result = zone "X" (low risk).
- Provider: `services/signal_providers/fema_nfhl.py` (shipped).

### 3. HUD Fair Market Rent (FMR)
- Endpoint: `https://www.huduser.gov/hudapi/public/fmr/data/{zip|fips}`
- Auth: free Bearer token (https://www.huduser.gov/portal/dataset/fmr-api.html).
- Mapping: `median_rent` = 2-bedroom FMR.
- Subject: zip.
- Notes: Annual cadence, very stable. Best baseline if no live rent feed.
- Provider: `services/signal_providers/hud_fmr.py` (shipped).

### 4. Census ACS 5-Year
- Endpoint: `https://api.census.gov/data/2022/acs/acs5?get=B25077_001E,B25064_001E&for=zip%20code%20tabulation%20area:60601&key=...`
- Auth: free key (https://api.census.gov/data/key_signup.html).
- Tables: `B25077_001E` (median home value), `B25064_001E` (median gross rent).
- Mapping: `median_sale_price`, `median_rent`.
- Subject: zip (ZCTA).
- Notes: Annual cadence. The single best free national source.
- Provider: `services/signal_providers/census_acs.py` (shipped).

### 5. GTFS / Transit stop density
- Sources: CTA (Chicago), MBTA (Boston), every major US transit agency publishes GTFS.
- Auth: none.
- Pipeline: download `stops.txt`, geocode by zip, count stops per zip → normalize 0–100.
- Mapping: `transit_score` (proxy).
- Notes: Walk Score / Transit Score products use this exact derivation. No license issue.

### 6. NCES schools (public school district scores)
- Endpoint: `https://nces.ed.gov/ccd/elsi/`
- Auth: none.
- Pipeline: aggregate school-level metrics (test scores, graduation) per district → join district → zip.
- Mapping: `school_score`.

### 7. Zillow Research bulk downloads
- Index files: ZHVI (home values), ZORI (rent index), ZILDI (days-on-market).
- URL format: `https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_bdrmcnt_3.csv`
- Auth: none, public CSV.
- Cadence: monthly.
- Mapping: `median_sale_price`, `median_rent`, time-on-market proxy.

### 8. Redfin Data Center
- URL: `https://redfin-public-data.s3-us-west-2.amazonaws.com/redfin_market_tracker/zip_code_market_tracker.tsv000.gz`
- Auth: none, public TSV.
- Mapping: `median_sale_price`, `inventory_pressure` (`new_listings/inventory`), time-on-market.

### 9. FRED (Federal Reserve Economic Data)
- Endpoint: `https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE30US&api_key=...`
- Auth: free key.
- Series of interest: `MORTGAGE30US`, `CSUSHPISA`, `MEDLISPRI`, `MEDDAYONMAR`.
- Mapping: macro context — write at `subject_type=jurisdiction`, `subject_id=us|<state>`.
- Provider: `services/signal_providers/fred.py` (shipped).

---

## Integration shape

All providers implement `MarketSignalProvider`:

```python
class MarketSignalProvider(Protocol):
    name: str
    async def fetch(self, **kwargs) -> Sequence[ExternalSignal]: ...
```

The CLI `scripts/fetch_external_signals.py --source chicago_crime` runs a
provider and upserts via `services.signal_writer.upsert_signal` — same
idempotent-per-day semantics as the backfill.

Adding a new source = ~50 lines: a class with `.name` and `.fetch`, plus a
test that mocks the HTTP response. No core changes required.

---

## Operational notes

- **Caching:** providers should not cache internally. Cache lives in
  `market_signals` itself — re-running `fetch_external_signals.py` daily is
  the cache-refresh pattern. Use `--observed-at` to backdate.
- **Failure mode:** providers raise on transport errors. The CLI catches
  per-provider so one failed source doesn't block the others.
- **Test convention:** real providers must be unit-tested with `httpx`
  mocked (`respx` or `monkeypatch`). Live calls go in
  `tests/integration/` and are skipped by default.
- **Subject ID conventions:** zip → `subject_type=neighborhood`,
  `subject_id=<zip>`; jurisdiction → `subject_type=jurisdiction`,
  `subject_id=us|jp|...`; property-specific → `subject_type=property`,
  `subject_id=<property.id>`.
