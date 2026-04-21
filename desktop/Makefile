SHELL := bash
PYTHON ?= python
REPORT_DIR ?= reports/code-quality
SCRIPT_ENV = PYTHON_BIN="$(PYTHON)" REPORT_DIR="$(REPORT_DIR)"
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_FILE := docker-compose.yml
ENV_FILE := ../.env

.PHONY: help lint format format-check type-check test security check-all \
        docker-up docker-down docker-restart docker-logs docker-build \
        docker-ps docker-clean docker-web docker-stop docker-shell

help:
	@echo "TradeAdviser Desktop - Makefile Commands"
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
	@echo "  make docker-up      - Start Docker containers (GUI mode)"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make docker-restart - Restart Docker containers"
	@echo "  make docker-logs    - View Docker container logs"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-ps      - List running containers"
	@echo "  make docker-clean   - Remove containers, volumes, and images"
	@echo "  make docker-web     - Start web/HTTP UI mode (noVNC)"
	@echo "  make docker-stop    - Stop web/HTTP UI containers"
	@echo "  make docker-shell   - Open shell in backend container"

lint:
	$(SCRIPT_ENV) bash tools/lint.sh

format:
	$(SCRIPT_ENV) bash tools/format.sh

format-check:
	$(SCRIPT_ENV) bash tools/format.sh --check

type-check:
	$(SCRIPT_ENV) bash tools/type_check.sh

test:
	$(SCRIPT_ENV) bash tools/test.sh

security:
	$(SCRIPT_ENV) bash tools/security_scan.sh

check-all: format-check lint type-check test security

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

