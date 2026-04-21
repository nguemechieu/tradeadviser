#!/bin/bash

# TradeAdviser Application Startup Script
# Unix/Linux/macOS Version
# Usage: ./scripts/start-app.sh [MODE]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default mode
MODE="${1:-dev}"
BUILD_FRONTEND=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        dev)
            MODE="dev"
            shift
            ;;
        docker)
            MODE="docker"
            shift
            ;;
        full)
            MODE="full"
            shift
            ;;
        --build-frontend)
            BUILD_FRONTEND=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

show_help() {
    cat << EOF
TradeAdviser Application Startup Script

USAGE:
    ./scripts/start-app.sh [MODE] [OPTIONS]

MODES:
    dev                 Start in development mode (default)
                        - Backend: Uvicorn with auto-reload
                        - Frontend: Vite dev server (separate)
                        - Database: SQLite
    
    docker              Start with Docker Compose
                        - All services in containers
                        - PostgreSQL database
                        - Single command to start all
    
    full                Start all services
                        - Backend and frontend in separate terminals
                        - Database: SQLite

OPTIONS:
    --build-frontend    Build frontend before starting backend
    --help              Display this help message

EXAMPLES:
    # Start in development mode
    ./scripts/start-app.sh dev
    
    # Start with Docker
    ./scripts/start-app.sh docker
    
    # Start all services
    ./scripts/start-app.sh full
    
    # Build frontend first
    ./scripts/start-app.sh dev --build-frontend

URLS:
    Frontend Dev:    http://localhost:5173 (Vite)
    Backend API:     http://localhost:8000
    API Docs:        http://localhost:8000/docs
    Docker:          http://localhost:8000 (frontend via backend)

REQUIREMENTS:
    - Python 3.10+
    - Node.js 18+
    - Docker & Docker Compose (for docker mode)
    - tmux or screen (optional, for running multiple processes)

TROUBLESHOOTING:
    Port already in use:
        lsof -i :8000
        kill -9 <PID>
    
    Permission denied:
        chmod +x scripts/start-app.sh
    
    Virtual environment issues:
        rm -rf backend/venv
        Then run script again

EOF
}

# Print header
echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       TradeAdviser Application Startup      ║${NC}"
echo -e "${CYAN}║              Sopotek Inc (c) 2026          ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check Python
echo -e "${CYAN}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | grep -oP '\d+\.\d+')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check Node.js
echo -e "${CYAN}Checking Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    exit 1
fi
NODE_VERSION=$(node --version | sed 's/v//')
echo -e "${GREEN}✓ Node.js ${NODE_VERSION} found${NC}"

cd "$PROJECT_ROOT"

# Create logs directory
mkdir -p logs

case "$MODE" in
    dev)
        echo ""
        echo -e "${GREEN}Starting TradeAdviser in Development Mode...${NC}"
        echo ""
        
        # Build frontend if requested
        if [ "$BUILD_FRONTEND" = true ]; then
            echo -e "${CYAN}Building frontend...${NC}"
            cd frontend
            npm run build
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Frontend build failed${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Frontend build successful${NC}"
            cd "$PROJECT_ROOT"
        fi
        
        # Setup Python virtual environment
        if [ ! -d "backend/venv" ]; then
            echo -e "${CYAN}Creating Python virtual environment...${NC}"
            cd backend
            python3 -m venv venv
            source venv/bin/activate
            pip install -q -r requirements.txt
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Failed to install backend dependencies${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"
            cd "$PROJECT_ROOT"
        fi
        
        # Setup frontend dependencies
        if [ ! -d "frontend/node_modules" ]; then
            echo -e "${CYAN}Installing frontend dependencies...${NC}"
            cd frontend
            npm install -q
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Failed to install frontend dependencies${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
            cd "$PROJECT_ROOT"
        fi
        
        # Copy env file if not exists
        if [ ! -f ".env.local" ]; then
            cp .env.example .env.local
            echo -e "${GREEN}✓ Created .env.local from template${NC}"
        fi
        
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Development Mode - Single Terminal        ║${NC}"
        echo -e "${GREEN}║  Backend will serve both API and Frontend  ║${NC}"
        echo -e "${GREEN}╠════════════════════════════════════════════╣${NC}"
        echo -e "${GREEN}║ Frontend:   http://localhost:8000          ║${NC}"
        echo -e "${GREEN}║ Backend:    http://localhost:8000/api      ║${NC}"
        echo -e "${GREEN}║ API Docs:   http://localhost:8000/docs     ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${CYAN}Starting backend (auto-reload enabled)...${NC}"
        echo ""
        
        cd backend
        source venv/bin/activate
        exec python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
        ;;
    
    docker)
        echo ""
        echo -e "${GREEN}Starting TradeAdviser with Docker Compose...${NC}"
        echo ""
        
        # Check Docker
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}✗ Docker not found${NC}"
            echo -e "${YELLOW}  Please install Docker from https://www.docker.com/get-docker${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Docker found${NC}"
        
        if ! command -v docker-compose &> /dev/null; then
            echo -e "${RED}✗ Docker Compose not found${NC}"
            echo -e "${YELLOW}  Please install Docker Compose${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Docker Compose found${NC}"
        
        # Copy env file if not exists
        if [ ! -f ".env.local" ]; then
            cp .env.example .env.local
            echo -e "${GREEN}✓ Created .env.local from template${NC}"
        fi
        
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Docker Compose Mode                       ║${NC}"
        echo -e "${GREEN}╠════════════════════════════════════════════╣${NC}"
        echo -e "${GREEN}║ Frontend:   http://localhost:8000          ║${NC}"
        echo -e "${GREEN}║ Backend:    http://localhost:8000/api      ║${NC}"
        echo -e "${GREEN}║ Database:   localhost:5432                 ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
        echo ""
        
        docker-compose up --build
        ;;
    
    full)
        echo ""
        echo -e "${GREEN}Starting TradeAdviser in Full Mode...${NC}"
        echo ""
        
        # Build frontend if requested
        if [ "$BUILD_FRONTEND" = true ]; then
            echo -e "${CYAN}Building frontend...${NC}"
            cd frontend
            npm run build
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Frontend build failed${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Frontend build successful${NC}"
            cd "$PROJECT_ROOT"
        fi
        
        # Setup Python virtual environment
        if [ ! -d "backend/venv" ]; then
            echo -e "${CYAN}Setting up backend...${NC}"
            cd backend
            python3 -m venv venv
            source venv/bin/activate
            pip install -q -r requirements.txt
            cd "$PROJECT_ROOT"
        fi
        
        # Setup frontend dependencies
        if [ ! -d "frontend/node_modules" ]; then
            echo -e "${CYAN}Setting up frontend...${NC}"
            cd frontend
            npm install -q
            cd "$PROJECT_ROOT"
        fi
        
        # Copy env file if not exists
        if [ ! -f ".env.local" ]; then
            cp .env.example .env.local
        fi
        
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Full Mode - Multiple Terminals            ║${NC}"
        echo -e "${GREEN}╠════════════════════════════════════════════╣${NC}"
        echo -e "${GREEN}║ Frontend:   http://localhost:5173          ║${NC}"
        echo -e "${GREEN}║ Backend:    http://localhost:8000          ║${NC}"
        echo -e "${GREEN}║ API Docs:   http://localhost:8000/docs     ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
        echo ""
        
        # Use tmux if available, otherwise use subshells
        if command -v tmux &> /dev/null; then
            echo -e "${CYAN}Using tmux for multiple terminals${NC}"
            
            # Create new tmux session
            tmux new-session -d -s tradeadviser -x 200 -y 50
            
            # Window 1: Backend
            tmux new-window -t tradeadviser -n "backend"
            tmux send-keys -t tradeadviser:backend "cd $PROJECT_ROOT/backend && source venv/bin/activate && python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0" Enter
            
            # Window 2: Frontend
            tmux new-window -t tradeadviser -n "frontend"
            tmux send-keys -t tradeadviser:frontend "cd $PROJECT_ROOT/frontend && npm run dev" Enter
            
            # Select backend window
            tmux select-window -t tradeadviser:backend
            
            # Attach to session
            tmux attach-session -t tradeadviser
        else
            echo -e "${YELLOW}tmux not found, using background processes${NC}"
            echo ""
            
            # Start backend in background
            cd "$PROJECT_ROOT"
            source backend/venv/bin/activate
            export PYTHONPATH="$PROJECT_ROOT"
            python -m uvicorn server.backend.main:app --reload --port 8000 --host 0.0.0.0 > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
            BACKEND_PID=$!
            echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
            echo "  Logs: tail -f logs/backend.log"
            
            # Start frontend in background
            cd "$PROJECT_ROOT/frontend"
            npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
            FRONTEND_PID=$!
            echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
            echo "  Logs: tail -f logs/frontend.log"
            
            echo ""
            echo -e "${CYAN}Application running. Press Ctrl+C to stop.${NC}"
            
            # Wait for Ctrl+C
            trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT
            wait
        fi
        ;;
    
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        show_help
        exit 1
        ;;
esac
