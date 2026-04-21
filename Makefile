.PHONY: help launch launch-full launch-backend launch-frontend launch-desktop launch-interactive \
        dev test lint format security docker logs clean install

# Color output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help:
	@echo ""
	@echo "$(CYAN)╔════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║         TradeAdviser Development Commands             ║$(RESET)"
	@echo "$(CYAN)╚════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(GREEN)📦 Launch Terminal Windows:$(RESET)"
	@echo "  make launch              - Interactive terminal launcher menu"
	@echo "  make launch-full         - Launch all services (Backend + Frontend + Desktop)"
	@echo "  make launch-backend      - Backend only (Docker + API)"
	@echo "  make launch-frontend     - Frontend only (React dev server)"
	@echo "  make launch-desktop      - Desktop only (PyQt application)"
	@echo ""
	@echo "$(GREEN)🚀 Quick Start:$(RESET)"
	@echo "  make dev                 - Start Backend + Frontend (Minimal setup)"
	@echo "  make install             - Install all dependencies"
	@echo ""
	@echo "$(GREEN)🧪 Code Quality:$(RESET)"
	@echo "  make test                - Run all tests"
	@echo "  make lint                - Run linters"
	@echo "  make format              - Format code"
	@echo "  make security            - Security scan"
	@echo ""
	@echo "$(GREEN)🐳 Docker Management:$(RESET)"
	@echo "  make docker              - Start Docker services"
	@echo "  make docker-down         - Stop Docker services"
	@echo "  make docker-logs         - View Docker logs"
	@echo "  make docker-clean        - Clean up Docker"
	@echo ""
	@echo "$(GREEN)📋 Utilities:$(RESET)"
	@echo "  make logs                - Watch all logs"
	@echo "  make clean               - Clean build artifacts"
	@echo ""

# ============================================================
# Terminal Launchers
# ============================================================

launch:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Interactive

launch-full:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Full

launch-backend:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Backend

launch-frontend:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Frontend

launch-desktop:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Desktop

launch-interactive:
	@powershell -NoProfile -ExecutionPolicy Bypass -File "./LAUNCH_TERMINALS.ps1" -Mode Interactive

# ============================================================
# Quick Start
# ============================================================

dev: docker frontend-install frontend-run
	@echo "$(GREEN)✓ Full stack running!$(RESET)"

install: backend-install frontend-install desktop-install
	@echo "$(GREEN)✓ All dependencies installed!$(RESET)"

# ============================================================
# Backend
# ============================================================

docker:
	@cd server && $(MAKE) docker-up

docker-down:
	@cd server && $(MAKE) docker-down

docker-logs:
	@cd server && $(MAKE) docker-logs

docker-clean:
	@cd server && $(MAKE) docker-clean

backend-install:
	@echo "$(CYAN)📦 Installing server dependencies...$(RESET)"
	@cd server && pip install -r requirements.txt

backend-lint:
	@cd server && $(MAKE) lint

backend-test:
	@cd server && $(MAKE) test

backend-security:
	@cd server && $(MAKE) security

# ============================================================
# Frontend
# ============================================================

frontend-install:
	@echo "$(CYAN)📦 Installing frontend dependencies...$(RESET)"
	@cd server/app/frontend && npm install

frontend-run:
	@echo "$(GREEN)⚛️  Starting frontend dev server...$(RESET)"
	@cd server/app/frontend && npm run dev

frontend-build:
	@echo "$(CYAN)🔨 Building frontend...$(RESET)"
	@cd server/app/frontend && npm run build

# ============================================================
# Desktop
# ============================================================

desktop-install:
	@echo "$(CYAN)📦 Installing desktop dependencies...$(RESET)"
	@cd desktop && python -m pip install -r requirements.txt

desktop-run:
	@echo "$(GREEN)🖥️  Starting desktop application...$(RESET)"
	@cd desktop && python main.py

# ============================================================
# Testing & Code Quality
# ============================================================

test:
	@echo "$(CYAN)🧪 Running all tests...$(RESET)"
	@cd server && $(MAKE) test
	@cd desktop && pytest

lint:
	@echo "$(CYAN)📋 Running linters...$(RESET)"
	@cd server && $(MAKE) lint

format:
	@echo "$(CYAN)🎨 Formatting code...$(RESET)"
	@cd server && $(MAKE) format

security:
	@echo "$(CYAN)🔒 Running security scan...$(RESET)"
	@cd server && $(MAKE) security

# ============================================================
# Utilities
# ============================================================

logs:
	@echo "$(CYAN)📋 Recent log files:$(RESET)"
	@find server/logs desktop/logs -name "*.log" -type f 2>/dev/null | \
		xargs ls -lht 2>/dev/null | head -10

clean:
	@echo "$(CYAN)🧹 Cleaning build artifacts...$(RESET)"
	@cd server && $(MAKE) docker-clean 2>/dev/null || true
	@rm -rf server/build server/dist server/*.egg-info
	@rm -rf desktop/build desktop/dist
	@rm -rf server/app/frontend/dist server/app/frontend/node_modules 2>/dev/null || true
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete!$(RESET)"

status:
	@echo "$(CYAN)📊 Service Status:$(RESET)"
	@echo ""
	@echo "  Backend (http://localhost:8000):"
	@curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "    ❌ Not running"
	@echo "  Frontend (http://localhost:5173):"
	@curl -s http://localhost:5173 2>/dev/null > /dev/null && echo "    ✓ Running" || echo "    ❌ Not running"
	@echo ""

# ============================================================
# Development Workflow
# ============================================================

.DEFAULT_GOAL := help

# Watch command for development
watch:
	@echo "$(CYAN)👀 Watching for changes...$(RESET)"
	@cd server && fswatch -r . --exclude ".*\.pyc" --exclude "__pycache__" | xargs -I {} $(MAKE) test

docs:
	@echo "$(CYAN)📚 Building documentation...$(RESET)"
	@cd desktop/docs && mkdocs serve
