# alembic/ — Database Migrations

## Purpose
Alembic migration infrastructure for async PostgreSQL schema management. Tracks all DDL changes to the database via versioned migration scripts.

## Key Files

| File | Role |
|------|------|
| `env.py` | Alembic bootstrap — async engine configuration, target metadata from `db/models.py` |
| `versions/` | Auto-generated and manual migration scripts |

## Commands
```bash
alembic upgrade head          # apply all pending migrations
alembic revision --autogenerate -m "description"  # generate new migration
alembic downgrade -1          # rollback one migration
alembic history               # show migration history
```

## Patterns
- **Async engine** — uses asyncpg driver matching the application
- **Autogenerate** — compares SQLAlchemy models against DB schema to produce migration diffs
- **UUID PKs + JSONB** — migrations handle PostgreSQL-specific column types
