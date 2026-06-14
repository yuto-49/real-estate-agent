# Market Signal Sources

Catalog of external data sources that can populate the `market_signals`
table. Schema reminder:
`market_signals(signal_type, subject_type, subject_id, value, payload, observed_at, source)`.
The `source` column should record which provider wrote the row.

The integration target is the `MarketSignalProvider` Protocol in
`services/signal_providers/base.py`. Each entry below tells you what's
available, what it costs, and which signal_type it can fill.

---

## Active Providers (Japan)

| Provider | Auth | Signal Types | Subject |
|---|---|---|---|
| **REINFOLIB Transaction (XIT001)** | `REINFOLIB_API_KEY` | `median_sale_price`, `median_unit_price` | `neighborhood` (municipality code) |
| **REINFOLIB Land Price (XPT002)** | `REINFOLIB_API_KEY` | `land_price_psm` | `neighborhood` (survey point) |
| **REINFOLIB Appraisal (XCT001)** | `REINFOLIB_API_KEY` | `appraised_value_psm` | `neighborhood` (address) |
| **REINFOLIB Hazard (XKT025/026/029)** | `REINFOLIB_API_KEY` | `hazard_liquefaction`, `hazard_flood`, `hazard_landslide` | `neighborhood` (mesh/tile) |
| **e-Stat** | `ESTAT_APP_ID` | various | `neighborhood` |

---

## Detail

### 1. REINFOLIB Transaction — XIT001

- Endpoint: `https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001`
- Auth: `Ocp-Apim-Subscription-Key` header.
- Parameters: `year`, `quarter`, `city` (5-digit municipality code), `priceClassification`.
- Mapping: aggregates `TradePrice` → `median_sale_price`, `UnitPrice` → `median_unit_price`.
- Subject: municipality (defaults to Tokyo 23 wards).
- Provider: `services/signal_providers/reinfolib_transaction.py`.

### 2. REINFOLIB Land Price — XPT002

- Endpoint: `https://www.reinfolib.mlit.go.jp/ex-api/external/XPT002`
- Auth: `Ocp-Apim-Subscription-Key` header.
- Parameters: `z`, `x`, `y` (XYZ tile coordinates), `year`, `response_format=geojson`.
- Mapping: `price` → `land_price_psm` (yen per m2).
- Payload includes: zoning, FAR/BCR, station distance, YoY change rate, coordinates.
- Subject: survey point ID.
- Provider: `services/signal_providers/reinfolib_land_price.py`.

### 3. REINFOLIB Appraisal — XCT001

- Endpoint: `https://www.reinfolib.mlit.go.jp/ex-api/external/XCT001`
- Auth: `Ocp-Apim-Subscription-Key` header.
- Parameters: `year`, `area` (prefecture codes), `division` (land-use: 00=residential, 05=commercial).
- Mapping: `L01_006` → `appraised_value_psm`.
- Payload includes: ~60 fields (zoning, road access, water/gas/sewer, station distance, coordinates).
- Subject: address or lat/lng.
- Provider: `services/signal_providers/reinfolib_appraisal.py`.

### 4. REINFOLIB Hazard — XKT025 / XKT026 / XKT029

- Endpoints: tile-based GeoJSON (XYZ coordinates, zoom 11-15).
- Auth: `Ocp-Apim-Subscription-Key` header.
- XKT025 (liquefaction): 6-level tendency → 0-10 score per mesh code.
- XKT026 (flood): inundation depth category → 0-10 score per tile.
- XKT029 (landslide): warning zone presence → binary 0/8 per tile.
- Default center: Tokyo (35.6762, 139.6503).
- Provider: `services/signal_providers/reinfolib_hazard.py`.

### 5. e-Stat (Japanese Government Statistics)

- Auth: `ESTAT_APP_ID`.
- Various statistical tables from Japanese government surveys.
- Provider: `services/signal_providers/estat.py`.

---

## Integration Shape

All providers implement `MarketSignalProvider`:

```python
class MarketSignalProvider(Protocol):
    name: str
    async def fetch(self, **kwargs) -> Sequence[ExternalSignal]: ...
```

The CLI `scripts/fetch_external_signals.py --source reinfolib_transaction`
runs a provider and upserts via `services.signal_writer.upsert_signal` —
same idempotent-per-day semantics as the backfill.

Adding a new source = ~50 lines: a class with `.name` and `.fetch`, plus a
test that mocks the HTTP response. No core changes required.

---

## Operational Notes

- **Caching:** providers should not cache internally. Cache lives in
  `market_signals` itself — re-running `fetch_external_signals.py` daily is
  the cache-refresh pattern. Use `--observed-at` to backdate.
- **Failure mode:** providers raise on transport errors. The CLI catches
  per-provider so one failed source doesn't block the others.
- **Test convention:** real providers must be unit-tested with `httpx`
  mocked (`httpx.MockTransport`). Live calls go in
  `tests/integration/` and are skipped by default.
- **Subject ID conventions:** municipality → `subject_type=neighborhood`,
  `subject_id=<5-digit code>`; property-specific → `subject_type=property`,
  `subject_id=<property.id>`.
