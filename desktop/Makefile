SHELL := bash
PYTHON ?= python
REPORT_DIR ?= reports/code-quality
SCRIPT_ENV = PYTHON_BIN="$(PYTHON)" REPORT_DIR="$(REPORT_DIR)"
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_FILE := docker-compose.yml
ENV_FILE := ../.env
VENV := .venv
VENV_ACTIVATE := $(VENV)/Scripts/activate

# Color output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

.PHONY: help launch dev setup install test lint format security check-all \
        docker-up docker-down docker-logs docker-ps docker-clean clean status \
        install-prod install-dev build-production production-check production-deploy

help:
	@echo ""
	@echo "$(CYAN)╔════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║    TradeAdviser Desktop - Development & Production    ║$(RESET)"
	@echo "$(CYAN)╚════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(GREEN)🚀 Quick Start:$(RESET)"
	@echo "  make launch         - Interactive launcher menu"
	@echo "  make dev            - Start desktop application (local)"
	@echo "  make setup          - Setup virtual environment"
	@echo "  make install        - Install dependencies"
	@echo ""
	@echo "$(GREEN)🧪 Testing & Quality:$(RESET)"
	@echo "  make test           - Run pytest"
	@echo "  make test-coverage  - Run tests with coverage report"
	@echo "  make lint           - Run linter checks"
	@echo "  make format         - Format code"
	@echo "  make security       - Run security scan"
	@echo "  make check-all      - Run all checks"
	@echo ""
	@echo "$(GREEN)🏭 Production:$(RESET)"
	@echo "  make install-prod   - Install production dependencies only"
	@echo "  make install-dev    - Install development dependencies (with prod)"
	@echo "  make build-production - Build production executable"
	@echo "  make production-check - Pre-deployment validation"
	@echo "  make production-deploy - Deploy to production"
	@echo ""
	@echo "$(GREEN)🐳 Docker Mode:$(RESET)"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make docker-logs    - View Docker logs (follow)"
	@echo "  make docker-ps      - List containers"
	@echo "  make docker-clean   - Remove containers & volumes"
	@echo ""
	@echo "$(GREEN)🛠️  Utilities:$(RESET)"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make status         - Show application status"
	@echo ""

# ============================================================
# Quick Start Commands
# ============================================================

launch:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_DESKTOP.ps1" -Mode Interactive

dev: install
	@echo "$(CYAN)▶ Starting desktop application...$(RESET)"
	@python main.py

setup:
	@echo "$(CYAN)🔧 Setting up virtual environment...$(RESET)"
	@python -m venv $(VENV)
	@$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel
	@$(VENV_ACTIVATE) && pip install -r requirements.txt
	@echo "$(GREEN)✓ Setup complete!$(RESET)"

install:
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(CYAN)Creating virtual environment...$(RESET)"; \
		python -m venv $(VENV); \
		$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel; \
	fi
	@echo "$(CYAN)Installing dependencies...$(RESET)"
	@$(VENV_ACTIVATE) && pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed!$(RESET)"

# ============================================================
# Production Installation
# ============================================================

install-prod:
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(CYAN)Creating virtual environment...$(RESET)"; \
		python -m venv $(VENV); \
		$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel; \
	fi
	@echo "$(CYAN)Installing production dependencies only...$(RESET)"
	@$(VENV_ACTIVATE) && pip install -r requirements-prod.txt
	@echo "$(GREEN)✓ Production dependencies installed!$(RESET)"

install-dev:
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(CYAN)Creating virtual environment...$(RESET)"; \
		python -m venv $(VENV); \
		$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel; \
	fi
	@echo "$(CYAN)Installing development dependencies...$(RESET)"
	@$(VENV_ACTIVATE) && pip install -r requirements-dev.txt
	@echo "$(GREEN)✓ Development dependencies installed!$(RESET)"

# ============================================================
# Testing
# ============================================================

test: install
	@echo "$(CYAN)🧪 Running tests...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -v

test-coverage: install
	@echo "$(CYAN)🧪 Running tests with coverage...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -v --cov=src --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report: htmlcov/index.html$(RESET)"

# ============================================================
# Code Quality
# ============================================================

lint: install
	@$(SCRIPT_ENV) bash tools/lint.sh

format: install
	@$(SCRIPT_ENV) bash tools/format.sh

format-check: install
	@$(SCRIPT_ENV) bash tools/format.sh --check

type-check: install
	@$(SCRIPT_ENV) bash tools/type_check.sh

security: install
	@$(SCRIPT_ENV) bash tools/security_scan.sh

check-all: format-check lint type-check test security
	@echo "$(GREEN)✓ All checks passed!$(RESET)"

################################################################################
# Docker Operations
################################################################################

# Verify .env file exists
.env-check:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "ERROR: .env file not found at $(ENV_FILE)"; \
		echo "Please copy .env.template to .env and update the values:"; \
		echo "  cp .env.template .env"; \
		exit 1; \
	fi

# Build Docker images
docker-build: .env-check
	@echo "Building Docker images..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) build --no-cache

# Start containers in GUI mode (default)
docker-up: .env-check
	@echo "Starting Docker containers (GUI mode)..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo ""
	@echo "Containers started! Checking status..."
	@sleep 3
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) ps

# Stop containers
docker-down: .env-check
	@echo "Stopping Docker containers..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) down

# Restart containers
docker-restart: .env-check
	@echo "Restarting Docker containers..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) restart

# View logs
docker-logs: .env-check
	@echo "Container logs (follow mode, press Ctrl+C to exit):"
	@echo ""
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) logs -f --tail=50

# List containers
docker-ps: .env-check
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) ps

# Start web/HTTP UI mode (noVNC)
docker-web: .env-check
	@echo "Starting Docker containers in WEB mode (noVNC)..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) --profile web up -d
	@echo ""
	@echo "Web UI starting up... waiting for services"
	@sleep 5
	@echo ""
	@echo "✓ PostgreSQL available at: localhost:5433"
	@echo "✓ API available at: http://localhost:8001"
	@echo "✓ noVNC Web UI available at: http://localhost:6080"
	@echo "✓ VNC available at: localhost:5900"
	@echo ""
	@echo "To view logs:"
	@echo "  make docker-logs"
	@echo ""
	@echo "To stop:"
	@echo "  make docker-stop"

# Stop web/HTTP UI containers
docker-stop: .env-check
	@echo "Stopping web/HTTP UI containers..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) --profile web down

# Clean up (remove containers, volumes, networks)
docker-clean: .env-check
	@echo "WARNING: This will remove all Docker containers, volumes, and networks"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Cleaning up Docker resources..."; \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) --profile web down -v; \
		echo "Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

# Shell access to backend container
docker-shell: .env-check
	@echo "Opening shell in backend container..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) exec backend bash

# ============================================================
# Utilities
# ============================================================

clean:
	@echo "$(CYAN)🧹 Cleaning build artifacts...$(RESET)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf dist/ build/ *.egg-info/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete!$(RESET)"

status:
	@echo ""
	@echo "$(CYAN)📊 Application Status:$(RESET)"
	@echo ""
	@echo "  Virtual Environment:"
	@if [ -d "$(VENV)" ]; then \
		echo "    ✓ Exists at $(VENV)"; \
	else \
		echo "    ✗ Not found (run: make install)"; \
	fi
	@echo ""
	@echo "  Main Entry Point:"
	@echo "    ✓ main.py (PyQt desktop application)"
	@echo ""
	@echo "  Logs:"
	@ls -lht logs/*.log 2>/dev/null | head -3 || echo "    No logs yet"
	@echo ""

# ============================================================
# Production Build & Deployment
# ============================================================

build-production: install-prod check-all
	@echo ""
	@echo "$(CYAN)🏗️  Building production executable...$(RESET)"
	@echo ""
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./build-production.ps1" -Version 1.0.0
	@echo ""
	@echo "$(GREEN)✓ Production build complete!$(RESET)"

production-check: install-prod
	@echo ""
	@echo "$(CYAN)🔍 Running production readiness checks...$(RESET)"
	@echo ""
	@echo "$(YELLOW)→ Checking configuration files...$(RESET)"
	@[ -f ".env" ] && echo "  ✓ .env file found" || echo "  ✗ .env file missing (required for production)"
	@[ -f ".env.example" ] && echo "  ✓ .env.example found" || echo "  ✗ .env.example missing"
	@echo ""
	@echo "$(YELLOW)→ Running tests...$(RESET)"
	@$(VENV_ACTIVATE) && pytest src/tests/test_main_entrypoint.py -v --tb=short || echo "  ✗ Critical tests failed"
	@echo ""
	@echo "$(YELLOW)→ Code quality checks...$(RESET)"
	@$(VENV_ACTIVATE) && black --check src/ 2>/dev/null && echo "  ✓ Code formatting OK" || echo "  ⚠ Code needs formatting"
	@echo ""
	@echo "$(YELLOW)→ Security scan...$(RESET)"
	@$(VENV_ACTIVATE) && bandit -r src/ -f csv -o /dev/null 2>/dev/null && echo "  ✓ Security OK" || echo "  ⚠ Security issues detected"
	@echo ""
	@echo "$(YELLOW)→ Environment configuration...$(RESET)"
	@echo "  Version: $(shell grep 'version' pyproject.toml | head -1)"
	@echo "  Python: $(shell python --version 2>&1)"
	@echo ""
	@echo "$(GREEN)✓ Production readiness check complete!$(RESET)"
	@echo ""

production-deploy:
	@echo ""
	@echo "$(CYAN)🚀 PRODUCTION DEPLOYMENT$(RESET)"
	@echo ""
	@echo "$(YELLOW)⚠️  This will deploy to production environment$(RESET)"
	@echo ""
	@echo "Pre-deployment checklist:"
	@echo "  ☐ Backups created"
	@echo "  ☐ Tests passing (make production-check)"
	@echo "  ☐ Release notes updated"
	@echo "  ☐ Configuration files ready (.env)"
	@echo "  ☐ Team notification sent"
	@echo ""
	@echo "Steps:"
	@echo "  1. Build production executable: make build-production"
	@echo "  2. Deploy to staging: copy dist/TradeAdviser.exe to staging"
	@echo "  3. Run smoke tests: verify broker connections, data feeds"
	@echo "  4. Deploy to production: copy to production server"
	@echo "  5. Verify: restart application and check logs"
	@echo ""
	@echo "For automated deployment, configure CI/CD pipeline in GitHub Actions"
	@echo ""

.DEFAULT_GOAL := help

