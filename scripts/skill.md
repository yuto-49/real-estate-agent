# scripts/ — CLI Utilities

## Purpose
Executable CLI scripts for database setup, data seeding, market signal backfill, and developer onboarding. All scripts are async and idempotent where possible.

## Key Files

| File | Role |
|------|------|
| `seed_tokyo.py` | Load REINS fixture data into Property table (idempotent by REINS ID) |
| `seed_from_csv.py` | Bulk import properties from CSV datasets |
| `seed_kaggle_usa.py` | Import US property data from Kaggle datasets |
| `seed_properties.py` | General property seeding utility |
| `create_dev_user.py` | Create development auth account via Supabase service role key |
| `backfill_market_signals.py` | Derive `median_sale_price` + `inventory_pressure` per zip and `hazard` per property from existing DB rows |
| `fetch_external_signals.py` | `--source <name>` runs one signal provider, upserts via shared writer; `--list` shows registered providers |
| `init-shared-db.sh` | Initialize shared PostgreSQL database |

## Patterns
- **Idempotent seeding:** Scripts check for existing records before inserting
- **Async CLI:** Uses `asyncio.run()` for database operations
- **Provider CLI:** `fetch_external_signals.py` delegates to registered signal providers
