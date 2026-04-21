SHELL := bash
PYTHON ?= python
REPORT_DIR ?= reports/code-quality
SCRIPT_ENV = PYTHON_BIN="$(PYTHON)" REPORT_DIR="$(REPORT_DIR)"
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_FILE := docker-compose.yml
ENV_FILE := ../.env

.PHONY: help lint format format-check type-check test security check-all \
        docker-up docker-down docker-restart docker-logs docker-build \
        docker-ps docker-clean docker-shell run dev

help:
	@echo "TradeAdviser Server - Makefile Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev            - Run development server"
	@echo "  make run            - Run production server"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Run linter checks"
	@echo "  make format         - Format code"
	@echo "  make format-check   - Check code formatting"
	@echo "  make type-check     - Run type checking"
	@echo "  make test           - Run tests"
	@echo "  make security       - Run security scan"
	@echo "  make check-all      - Run all checks"
	@echo ""
	@echo "Docker Operations:"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make docker-restart - Restart Docker containers"
	@echo "  make docker-logs    - View Docker container logs"
	@echo "  make docker-ps      - List running containers"
	@echo "  make docker-clean   - Remove containers and volumes"
	@echo "  make docker-shell   - Open shell in API container"

lint:
	$(SCRIPT_ENV) bash tools/lint.sh || true

format:
	$(SCRIPT_ENV) bash tools/format.sh || true

format-check:
	$(SCRIPT_ENV) bash tools/format.sh --check || true

type-check:
	$(SCRIPT_ENV) bash tools/type_check.sh || true

test:
	$(SCRIPT_ENV) bash tools/test.sh || true

security:
	$(SCRIPT_ENV) bash tools/security_scan.sh || true

check-all: format-check lint type-check test security

################################################################################
# Development & Runtime
################################################################################

dev:
	@echo "Starting TradeAdviser Server (Development Mode)..."
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

run:
	@echo "Starting TradeAdviser Server (Production Mode)..."
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

################################################################################
# Docker Operations
################################################################################

# Verify .env file exists
.env-check:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "ERROR: .env file not found at $(ENV_FILE)"; \
		echo "Please copy .env.template to .env and update the values:"; \
		echo "  cp ../.env.template ../.env"; \
		exit 1; \
	fi

# Build Docker images
docker-build: .env-check
	@echo "Building Docker images for server..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) build --no-cache

# Start containers
docker-up: .env-check
	@echo "Starting Docker containers..."
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

# Clean up
docker-clean: .env-check
	@echo "WARNING: This will remove all Docker containers and volumes"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Cleaning up Docker resources..."; \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) down -v; \
		echo "Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

# Shell access to API container
docker-shell: .env-check
	@echo "Opening shell in API container..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) exec api bash
