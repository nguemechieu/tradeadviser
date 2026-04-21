#!/bin/bash

# TradeAdviser Desktop - Bash Launch Wrapper
# For macOS/Linux users who prefer bash

set -e

DESKTOP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$DESKTOP_ROOT/.venv"
MAIN_SCRIPT="$DESKTOP_ROOT/main.py"

# Colors
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo "========================================================"
    echo "  $1"
    echo "========================================================"
    echo ""
}

print_status() {
    echo -e "  → $1"
}

check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}ERROR: Virtual environment not found at $VENV_PATH${NC}"
        echo ""
        echo "Please create virtual environment first:"
        echo "  cd $DESKTOP_ROOT"
        echo "  python -m venv .venv"
        echo "  source .venv/bin/activate"
        echo "  pip install -r requirements.txt"
        echo ""
        exit 1
    fi
}

check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        echo -e "  ✓ $PYTHON_VERSION"
    else
        echo -e "${RED}ERROR: Python not found${NC}"
        exit 1
    fi
    
    # Check PyQt6
    if python3 -c "import PyQt6" 2>/dev/null; then
        echo "  ✓ PyQt6: Installed"
    else
        echo -e "${YELLOW}WARNING: PyQt6 not installed${NC}"
        echo "  Run: pip install -r requirements.txt"
    fi
    
    echo ""
}

launch_dev() {
    print_header "TradeAdviser Desktop - Development Mode"
    
    check_venv
    
    print_status "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    
    check_dependencies
    
    print_status "Starting desktop application..."
    echo ""
    
    python "$MAIN_SCRIPT"
}

launch_test() {
    print_header "TradeAdviser Desktop - Test Mode"
    
    check_venv
    
    print_status "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    
    check_dependencies
    
    print_status "Running tests..."
    echo ""
    
    pytest -v --cov=src --cov-report=html
    
    echo ""
    echo -e "${GREEN}✓ Test report: htmlcov/index.html${NC}"
}

setup_venv() {
    print_header "TradeAdviser Desktop - Virtual Environment Setup"
    
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    
    print_status "Activating and installing dependencies..."
    source "$VENV_PATH/bin/activate"
    
    echo ""
    pip install --upgrade pip setuptools wheel
    pip install -r "$DESKTOP_ROOT/requirements.txt"
    
    echo ""
    echo -e "${GREEN}✓ Setup complete!${NC}"
    echo -e "${CYAN}Next: Run this script again to start the app${NC}"
}

show_menu() {
    print_header "TradeAdviser Desktop Application Launcher"
    
    echo "Select launch mode:"
    echo ""
    echo "  [1]  Development    (Local PyQt application)"
    echo "  [2]  Test           (Run pytest suite)"
    echo "  [3]  Setup          (Create/update virtual environment)"
    echo "  [0]  Exit"
    echo ""
    
    read -p "Enter selection (0-3): " selection
    
    case "$selection" in
        1) launch_dev ;;
        2) launch_test ;;
        3) setup_venv ;;
        0) echo "Exiting..."; exit 0 ;;
        *) echo "Invalid selection."; exit 1 ;;
    esac
}

# Main execution
if [ "$1" == "--dev" ]; then
    launch_dev
elif [ "$1" == "--test" ]; then
    launch_test
elif [ "$1" == "--setup" ]; then
    setup_venv
else
    show_menu
fi

echo ""
