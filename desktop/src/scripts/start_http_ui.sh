#!/bin/bash

<<<<<<< Updated upstream
=======
##############################################################################
# TradeAdviser Desktop - HTTP UI Startup Script
# 
# This script starts the desktop application in HTTP/VNC mode using Xvfb
# (virtual framebuffer), VNC server, and noVNC for browser-based access.
##############################################################################

>>>>>>> Stashed changes
set -e

echo "Starting Sopotek Quant HTTP UI..."

<<<<<<< Updated upstream
# Default values (can be overridden by env)
DISPLAY_NUM=${DISPLAY:-:99}
SCREEN_WIDTH=${SCREEN_WIDTH:-1600}
SCREEN_HEIGHT=${SCREEN_HEIGHT:-900}
SCREEN_DEPTH=${SCREEN_DEPTH:-24}

VNC_PORT=${VNC_PORT:-5900}
NOVNC_PORT=${NOVNC_PORT:-6080}

echo "Display: $DISPLAY_NUM"
echo "Resolution: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}"

# Start virtual framebuffer
echo "Starting Xvfb..."
Xvfb $DISPLAY_NUM -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} &

sleep 2

export DISPLAY=$DISPLAY_NUM

# Start window manager
echo "Starting Fluxbox..."
fluxbox &

sleep 2

# Start VNC server
echo "Starting x11vnc..."
x11vnc -display $DISPLAY -nopw -forever -shared -rfbport $VNC_PORT &

sleep 2

# Start noVNC (web access)
echo "Starting noVNC on port $NOVNC_PORT..."
websockify --web=/usr/share/novnc/ $NOVNC_PORT localhost:$VNC_PORT &

sleep 2

echo "Launching Sopotek Quant UI..."
sopotek_quant_system

# Keep container alive if app exits
wait
=======
APP_HOME="/app"
LOG_DIR="${APP_HOME}/logs"
LOG_FILE="${LOG_DIR}/http-ui-$(date +%Y%m%d_%H%M%S).log"

mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "TradeAdviser Desktop - HTTP UI Mode"
log "=========================================="

export DISPLAY="${DISPLAY}"
export PYTHONPATH="${APP_HOME}:${APP_HOME}/desktop/src:${PYTHONPATH}"
export PYTHONUNBUFFERED=1
export QT_X11_NO_MITSHM=1
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1
export QT_OPENGL=software
export QT_QUICK_BACKEND=software
export QSG_RHI_BACKEND=software
export QT_XCB_GL_INTEGRATION=none
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-gpu-rasterization --disable-dev-shm-usage --disable-features=Vulkan,VulkanFromANGLE,UseSkiaRenderer"

log "Starting application..."
cd "${APP_HOME}"
python -m desktop.main
>>>>>>> Stashed changes
