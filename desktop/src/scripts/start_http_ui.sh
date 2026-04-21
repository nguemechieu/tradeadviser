#!/bin/bash

##############################################################################
# TradeAdviser Desktop - HTTP UI Startup Script
# 
# This script starts the desktop application in HTTP/VNC mode using Xvfb
# (virtual framebuffer), VNC server, and noVNC for browser-based access.
#
# Environment Variables:
#   - DISPLAY: X11 display number (default: :99)
#   - SCREEN_WIDTH: Virtual screen width (default: 1600)
#   - SCREEN_HEIGHT: Virtual screen height (default: 900)
#   - SCREEN_DEPTH: Virtual screen color depth (default: 24)
#   - VNC_PORT: VNC server port (default: 5900)
#   - NOVNC_PORT: noVNC web UI port (default: 6080)
#   - LOG_LEVEL: Application log level (default: info)
##############################################################################

set -e

# Configuration
DISPLAY="${DISPLAY:-:99}"
SCREEN_WIDTH="${SCREEN_WIDTH:-1600}"
SCREEN_HEIGHT="${SCREEN_HEIGHT:-900}"
SCREEN_DEPTH="${SCREEN_DEPTH:-24}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
LOG_LEVEL="${LOG_LEVEL:-info}"

# Paths
APP_HOME="/app"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="${APP_HOME}/logs"
LOG_FILE="${LOG_DIR}/http-ui-$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "TradeAdviser Desktop - HTTP UI Mode"
log "=========================================="
log "Display: ${DISPLAY}"
log "Screen: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}"
log "VNC Port: ${VNC_PORT}"
log "noVNC Port: ${NOVNC_PORT}"
log "Log File: ${LOG_FILE}"
log "=========================================="

# Cleanup function
cleanup() {
    log "Shutting down..."
    # Kill all child processes
    pkill -P $$ || true
    wait
    log "Shutdown complete"
}

trap cleanup EXIT INT TERM

# Check if Xvfb is available
if ! command -v Xvfb &> /dev/null; then
    log "ERROR: Xvfb not found. Installing xvfb..."
    apt-get update -qq
    apt-get install -y -qq xvfb x11-utils xfonts-100dpi xfonts-75dpi xfonts-encodings xfonts-utils fontconfig
fi

# Check if VNC server is available
if ! command -v vncserver &> /dev/null; then
    log "ERROR: VNC server not found. Installing tigervnc-server..."
    apt-get update -qq
    apt-get install -y -qq tigervnc-server
fi

# Check if noVNC is available
if [ ! -d "/opt/novnc" ]; then
    log "Installing noVNC..."
    mkdir -p /opt
    cd /opt
    git clone --depth 1 https://github.com/novnc/noVNC.git 2>&1 | tee -a "${LOG_FILE}"
    cd noVNC
    git clone --depth 1 https://github.com/novnc/websockify websockify 2>&1 | tee -a "${LOG_FILE}"
    chmod +x /opt/noVNC/utils/launch.sh
fi

# Start Xvfb (virtual framebuffer)
log "Starting Xvfb on ${DISPLAY}..."
Xvfb "${DISPLAY}" \
    -screen 0 "${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}" \
    -ac \
    -listen unix \
    +extension GLX \
    +render \
    -noreset \
    >> "${LOG_FILE}" 2>&1 &
XVFB_PID=$!
log "Xvfb started (PID: ${XVFB_PID})"

# Wait for Xvfb to be ready
sleep 2

# Set DISPLAY for child processes
export DISPLAY="${DISPLAY}"

# Create VNC directory
mkdir -p ~/.vnc
cat > ~/.vnc/xstartup <<'XSTARTUP'
#!/bin/bash
xsetroot -solid grey
export LC_ALL=C
export LANG=C
exec "$@"
XSTARTUP
chmod +x ~/.vnc/xstartup

# Start VNC server
log "Starting VNC server on port ${VNC_PORT}..."
vncserver "${DISPLAY}" \
    -geometry "${SCREEN_WIDTH}x${SCREEN_HEIGHT}" \
    -depth "${SCREEN_DEPTH}" \
    -rfbport "${VNC_PORT}" \
    -securitytypes none \
    -noreverse \
    -dontdisconnect \
    >> "${LOG_FILE}" 2>&1 &
VNC_PID=$!
log "VNC server started (PID: ${VNC_PID})"

sleep 2

# Start noVNC
log "Starting noVNC on port ${NOVNC_PORT}..."
cd /opt/noVNC
./utils/launch.sh \
    --listen "${NOVNC_PORT}" \
    --vnc "localhost:${VNC_PORT}" \
    --web /opt/noVNC \
    >> "${LOG_FILE}" 2>&1 &
NOVNC_PID=$!
log "noVNC started (PID: ${NOVNC_PID})"

sleep 2

# Prepare Python environment
export PYTHONPATH="${APP_HOME}:${APP_HOME}/desktop/src:${PYTHONPATH}"
export PYTHONUNBUFFERED=1

# Set Qt environment variables for headless operation
export QT_X11_NO_MITSHM=1
export QT_QPA_PLATFORM=xcb
export QT_QPA_PLATFORM_PLUGIN_PATH=/opt/qt/plugins
export LIBGL_ALWAYS_SOFTWARE=1
export QT_OPENGL=software
export QT_QUICK_BACKEND=software
export QSG_RHI_BACKEND=software
export QT_XCB_GL_INTEGRATION=none
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-gpu-rasterization --disable-dev-shm-usage --disable-features=Vulkan,VulkanFromANGLE,UseSkiaRenderer"

# Start the TradeAdviser Desktop application
log "Starting TradeAdviser Desktop application..."
log "Command: python -m desktop.main"
log "=========================================="

cd "${APP_HOME}"

# Run the application with error handling
if python -m desktop.main >> "${LOG_FILE}" 2>&1; then
    log "Application exited normally"
else
    EXIT_CODE=$?
    log "Application exited with code: ${EXIT_CODE}"
    exit ${EXIT_CODE}
fi

# Keep the container running if app exits
log "Application stopped. Keeping container running..."
sleep infinity

