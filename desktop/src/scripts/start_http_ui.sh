#!/bin/bash

set -e

echo "Starting Sopotek Quant HTTP UI..."

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
