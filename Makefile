# ──────────────────────────────────────────────────────────────────────────────
# Enceladus Mission Control — Makefile
# Run `make help` to see all targets.
# ──────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
.PHONY: help \
        install install-backend install-frontend \
        dev dev-backend dev-frontend stop restart \
        test test-unit test-api test-astar test-sim test-verbose \
        lint lint-backend \
        build build-frontend \
        docker-up docker-down docker-logs docker-ps docker-rebuild \
        clean clean-backend clean-frontend clean-all \
        env-check openapi-dump \
        migrate migrate-create migrate-rollback migrate-history

# ── Ports ─────────────────────────────────────────────────────────────────────
BACKEND_PORT  := 8000
FRONTEND_PORT := 5173

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    := $(shell pwd)
BACKEND := $(ROOT)/backend
FRONTEND:= $(ROOT)/frontend
INFRA   := $(ROOT)/infra

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD  := \033[1m
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@printf '$(BOLD)Enceladus Mission Control$(RESET)\n\n'
	@printf '$(CYAN)Usage:$(RESET)  make <target>\n\n'
	@printf '$(CYAN)Targets:$(RESET)\n'
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { \
		printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2 \
	}' $(MAKEFILE_LIST)
	@printf '\n$(CYAN)Quick start (local, no Docker):$(RESET)\n'
	@printf '  make install   →  set up backend + frontend\n'
	@printf '  make dev       →  start both servers (auto-stops previous)\n'
	@printf '  make stop      →  kill dev servers on ports 8000 + 5173\n'
	@printf '  make restart   →  stop then start fresh\n'
	@printf '  make test      →  run all backend tests\n'
	@printf '\n$(CYAN)Quick start (Docker):$(RESET)\n'
	@printf '  make docker-up →  start full stack\n\n'

# ──────────────────────────────────────────────────────────────────────────────
# INSTALL / SETUP
# ──────────────────────────────────────────────────────────────────────────────

install: install-backend install-frontend ## Install all dependencies (backend + frontend)

install-backend: ## Install backend deps via uv
	@printf '$(BOLD)→ Installing backend dependencies$(RESET)\n'
	cd $(BACKEND) && uv sync
	@[ -f $(BACKEND)/.env ] || (cp $(BACKEND)/.env.example $(BACKEND)/.env && \
		printf '$(GREEN)Created backend/.env from .env.example$(RESET)\n')

install-frontend: ## Install frontend deps via npm
	@printf '$(BOLD)→ Installing frontend dependencies$(RESET)\n'
	cd $(FRONTEND) && npm install

# ──────────────────────────────────────────────────────────────────────────────
# DEVELOPMENT SERVERS
# ──────────────────────────────────────────────────────────────────────────────

dev: stop ## Start backend and frontend (stops any existing processes first)
	@printf '$(BOLD)→ Starting backend + frontend$(RESET)\n'
	@printf '  Backend : http://localhost:$(BACKEND_PORT)\n'
	@printf '  Frontend: http://localhost:$(FRONTEND_PORT)\n'
	@printf '  API docs: http://localhost:$(BACKEND_PORT)/docs\n\n'
	@(trap 'kill 0' SIGINT; \
	  $(MAKE) --no-print-directory dev-backend & \
	  sleep 1 && $(MAKE) --no-print-directory dev-frontend; \
	  wait)

dev-backend: ## Start the FastAPI dev server (hot-reload)
	cd $(BACKEND) && uv run uvicorn main:app \
		--reload \
		--host 0.0.0.0 \
		--port $(BACKEND_PORT)

dev-frontend: ## Start the Vite dev server
	cd $(FRONTEND) && npm run dev

stop: ## Kill any process running on the backend/frontend ports
	@printf '$(BOLD)→ Stopping dev servers$(RESET)\n'
	@PIDS=$$(lsof -ti:$(BACKEND_PORT) 2>/dev/null); \
		if [ -n "$$PIDS" ]; then \
			echo "$$PIDS" | xargs kill -9 2>/dev/null; \
			printf '  Stopped process on port $(BACKEND_PORT)\n'; \
		else \
			printf '  Port $(BACKEND_PORT) already free\n'; \
		fi
	@PIDS=$$(lsof -ti:$(FRONTEND_PORT) 2>/dev/null); \
		if [ -n "$$PIDS" ]; then \
			echo "$$PIDS" | xargs kill -9 2>/dev/null; \
			printf '  Stopped process on port $(FRONTEND_PORT)\n'; \
		else \
			printf '  Port $(FRONTEND_PORT) already free\n'; \
		fi

restart: stop dev ## Stop running servers then start fresh

# ──────────────────────────────────────────────────────────────────────────────
# TESTING
# ──────────────────────────────────────────────────────────────────────────────

test: ## Run all backend tests
	@printf '$(BOLD)→ Running all tests$(RESET)\n'
	cd $(BACKEND) && uv run pytest

test-verbose: ## Run all tests with verbose output
	cd $(BACKEND) && uv run pytest -v

test-unit: ## Run unit tests only (astar + simulation models + aegis + comm windows)
	cd $(BACKEND) && uv run pytest tests/test_astar.py tests/test_simulation.py tests/test_aegis.py tests/test_comm_windows.py -v

test-api: ## Run API integration tests
	cd $(BACKEND) && uv run pytest tests/test_mission_api.py -v

test-astar: ## Run A* pathfinding tests only
	cd $(BACKEND) && uv run pytest tests/test_astar.py -v

test-sim: ## Run simulation + anomaly engine tests
	cd $(BACKEND) && uv run pytest tests/test_simulation.py -v

test-watch: ## Re-run tests on file change (requires pytest-watch)
	cd $(BACKEND) && uv run ptw -- -v

# ──────────────────────────────────────────────────────────────────────────────
# LINTING / TYPE CHECKING
# ──────────────────────────────────────────────────────────────────────────────

lint: lint-backend ## Run all linters

lint-backend: ## Lint backend with ruff (if installed)
	@printf '$(BOLD)→ Linting backend$(RESET)\n'
	cd $(BACKEND) && uv run ruff check . || true

typecheck: ## Type-check backend with mypy (if installed)
	cd $(BACKEND) && uv run mypy . || true

# ──────────────────────────────────────────────────────────────────────────────
# BUILDING
# ──────────────────────────────────────────────────────────────────────────────

build: build-frontend ## Build all artefacts

build-frontend: ## Build the frontend for production
	@printf '$(BOLD)→ Building frontend$(RESET)\n'
	cd $(FRONTEND) && npm run build

# ──────────────────────────────────────────────────────────────────────────────
# DOCKER
# ──────────────────────────────────────────────────────────────────────────────

docker-up: ## Start the full stack (postgres + redis + backend + frontend)
	@printf '$(BOLD)→ Starting Docker stack$(RESET)\n'
	docker compose -f $(INFRA)/docker-compose.yml up

docker-up-d: ## Start the full stack in detached mode
	docker compose -f $(INFRA)/docker-compose.yml up -d
	@printf '$(GREEN)Stack running — services:$(RESET)\n'
	@printf '  Frontend : http://localhost:5173\n'
	@printf '  Backend  : http://localhost:8000\n'
	@printf '  API docs : http://localhost:8000/docs\n'
	@printf '  Postgres : localhost:5432\n'
	@printf '  Redis    : localhost:6379\n'

docker-down: ## Stop and remove containers (preserves volumes)
	docker compose -f $(INFRA)/docker-compose.yml down

docker-down-v: ## Stop containers and delete volumes (destructive)
	docker compose -f $(INFRA)/docker-compose.yml down -v

docker-logs: ## Tail logs from all containers
	docker compose -f $(INFRA)/docker-compose.yml logs -f

docker-logs-backend: ## Tail backend logs only
	docker compose -f $(INFRA)/docker-compose.yml logs -f backend

docker-ps: ## Show running container status
	docker compose -f $(INFRA)/docker-compose.yml ps

docker-rebuild: ## Rebuild images from scratch then start
	docker compose -f $(INFRA)/docker-compose.yml up --build --force-recreate

docker-shell-backend: ## Open a shell in the running backend container
	docker compose -f $(INFRA)/docker-compose.yml exec backend /bin/sh

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

env-check: ## Verify required tools are installed
	@printf '$(BOLD)→ Checking environment$(RESET)\n'
	@command -v uv      >/dev/null 2>&1 && printf '  $(GREEN)✓$(RESET) uv       ' && uv --version      || printf '  ✗ uv       NOT FOUND (curl -LsSf https://astral.sh/uv/install.sh | sh)\n'
	@command -v python3 >/dev/null 2>&1 && printf '  $(GREEN)✓$(RESET) python3  ' && python3 --version || printf '  ✗ python3  NOT FOUND\n'
	@command -v node    >/dev/null 2>&1 && printf '  $(GREEN)✓$(RESET) node     ' && node --version    || printf '  ✗ node     NOT FOUND\n'
	@command -v npm     >/dev/null 2>&1 && printf '  $(GREEN)✓$(RESET) npm      ' && npm --version     || printf '  ✗ npm      NOT FOUND\n'
	@command -v docker  >/dev/null 2>&1 && printf '  $(GREEN)✓$(RESET) docker   ' && docker --version  || printf '  ✗ docker   NOT FOUND (optional)\n'

openapi-dump: ## Dump OpenAPI spec to file (server must be running)
	@printf '$(BOLD)→ Fetching OpenAPI spec$(RESET)\n'
	curl -s http://localhost:8000/openapi.json | python3 -m json.tool > openapi.json
	@printf '$(GREEN)Saved to openapi.json$(RESET)\n'

# ──────────────────────────────────────────────────────────────────────────────
# DATABASE MIGRATIONS (Alembic)
# ──────────────────────────────────────────────────────────────────────────────

migrate: ## Apply all pending Alembic migrations
	@printf '$(BOLD)→ Applying database migrations$(RESET)\n'
	cd $(BACKEND) && uv run alembic upgrade head

migrate-create: ## Create a new migration: make migrate-create MSG="add user table"
	@[ -n "$(MSG)" ] || (printf '$(BOLD)Usage: make migrate-create MSG="<description>"$(RESET)\n'; exit 1)
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Roll back one migration step
	@printf '$(BOLD)→ Rolling back last migration$(RESET)\n'
	cd $(BACKEND) && uv run alembic downgrade -1

migrate-history: ## Show migration history
	cd $(BACKEND) && uv run alembic history --verbose

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

add-backend-dep: ## Add a backend dependency: make add-backend-dep PKG=<name>
	@[ -n "$(PKG)" ] || (printf '$(BOLD)Usage: make add-backend-dep PKG=<package-name>$(RESET)\n'; exit 1)
	cd $(BACKEND) && uv add $(PKG)
	@printf '$(GREEN)→ Remember to update README.md if this changes setup requirements$(RESET)\n'

# ──────────────────────────────────────────────────────────────────────────────
# CLEAN
# ──────────────────────────────────────────────────────────────────────────────

clean: clean-backend clean-frontend ## Remove build artefacts (keeps deps)

clean-backend: ## Remove Python cache files
	find $(BACKEND) -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf $(BACKEND)/.pytest_cache 2>/dev/null || true

clean-frontend: ## Remove frontend build output
	rm -rf $(FRONTEND)/dist 2>/dev/null || true

clean-all: clean ## Also remove virtual env and node_modules
	rm -rf $(BACKEND)/.venv 2>/dev/null || true
	rm -rf $(FRONTEND)/node_modules 2>/dev/null || true
	@printf '$(GREEN)Full clean done — run `make install` to restore$(RESET)\n'
