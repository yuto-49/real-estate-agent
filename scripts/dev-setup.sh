#!/usr/bin/env bash
# One-command development environment bootstrap.
# Usage: bash scripts/dev-setup.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo "=== Real Estate Agentic Platform — Dev Setup ==="
echo ""

# ---- Check prerequisites ----
command -v python >/dev/null 2>&1 || fail "Python not found. Install Python 3.11+"
command -v node   >/dev/null 2>&1 || fail "Node.js not found. Install Node 20+"
command -v npm    >/dev/null 2>&1 || fail "npm not found."

PY_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)

echo "Python: $PY_VER"
echo "Node:   $(node -v)"

# ---- .env file ----
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    info "Created .env from .env.example — edit it with your API keys"
  else
    warn "No .env.example found, skipping .env creation"
  fi
else
  info ".env already exists"
fi

# ---- Backend dependencies ----
echo ""
echo "Installing Python dependencies..."
pip install -e ".[dev]" --quiet
info "Python dependencies installed"

# ---- Frontend dependencies ----
echo ""
echo "Installing frontend dependencies..."
cd frontend && npm install --silent && cd ..
info "Frontend dependencies installed"

# ---- Pre-commit (optional) ----
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit install --quiet
  info "Pre-commit hooks installed"
else
  warn "pre-commit not found — run 'pip install pre-commit && pre-commit install' to enable hooks"
fi

# ---- Database ----
echo ""
if command -v docker >/dev/null 2>&1; then
  echo "Checking Docker containers..."
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q postgres; then
    info "Postgres container is running"
    echo "Running database init..."
    bash scripts/init-shared-db.sh 2>/dev/null && info "Database initialized" || warn "DB init failed — may already be initialized"
    echo "Running migrations..."
    alembic upgrade head 2>/dev/null && info "Migrations applied" || warn "Migrations failed — check DATABASE_URL in .env"
    echo "Seeding properties..."
    python scripts/seed_properties.py 2>/dev/null && info "Properties seeded" || warn "Seeding failed — may already be seeded"
  else
    warn "Postgres not running. Start it with: make infra"
  fi
else
  warn "Docker not found — database setup skipped"
fi

# ---- Summary ----
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (ANTHROPIC_API_KEY, SUPABASE_URL, etc.)"
echo "  2. Start infra:    make infra"
echo "  3. Start backend:  make dev-backend"
echo "  4. Start frontend: make dev-frontend"
echo "  5. Open http://localhost:5173"
echo ""
