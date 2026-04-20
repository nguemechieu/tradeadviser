FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/app/src

WORKDIR /app

# Install system dependencies needed by the desktop runtime and browser profile.
RUN apt-get update && apt-get install -y --no-install-recommends \
    autocutsel \
    build-essential \
    ca-certificates \
    curl \
    fluxbox \
    libasound2 \
    libdbus-1-3 \
    libegl1 \
    libfontconfig1 \
    libfreetype6 \
    libgl1 \
    libglib2.0-0 \
    libnss3 \
    libopengl0 \
    libportaudio2 \
    libpulse0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxrender1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxtst6 \
    novnc \
    openssl \
    websockify \
    x11-utils \
    x11vnc \
    xauth \
    xclip \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY sqs_desktop/pyproject.toml ./pyproject.toml
COPY sqs_desktop/README.md ./README.md
COPY sqs_desktop/src ./src
COPY shared ./shared

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install ".[ui,brokers,ml]" "psycopg[binary]>=3.2" PyJWT keyring

RUN sed -i 's/\r$//' /app/src/scripts/start_http_ui.sh 2>/dev/null || true && \
    chmod +x /app/src/scripts/start_http_ui.sh 2>/dev/null || true && \
    mkdir -p /app/data /app/logs /app/output

CMD ["sopotek_quant_system"]
