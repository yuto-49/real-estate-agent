#!/usr/bin/env bash
# Create the 'realestate' database in the shared dev-postgres container.
# Usage: bash scripts/init-shared-db.sh

set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-dev-postgres}"
DB_NAME="${POSTGRES_DB:-realestate}"
DB_USER="${POSTGRES_USER:-dev}"

echo "Creating database '$DB_NAME' in container '$CONTAINER'..."

# Create database if it doesn't already exist
docker exec "$CONTAINER" psql -U "$DB_USER" -tc \
  "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" \
  | grep -q 1 \
  && echo "Database '$DB_NAME' already exists." \
  || { docker exec "$CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" \
       && echo "Database '$DB_NAME' created."; }
