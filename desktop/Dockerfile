FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies needed by the desktop runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    autocutsel \
    bash \
    build-essential \
    ca-certificates \
    curl \
    fluxbox \
<<<<<<< HEAD
    gcc \
=======
<<<<<<< Updated upstream
=======
    gcc \
    git \
>>>>>>> Stashed changes
>>>>>>> 4bef926f634c72a86f231ee2b5ab2e56b52111ef
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
    postgresql-client \
    python3-dev \
    websockify \
    x11-utils \
    x11vnc \
    xauth \
    xclip \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY desktop/requirements-docker.txt ./requirements.txt
COPY desktop/__init__.py ./__init__.py
COPY desktop/main.py ./main.py
COPY desktop/src ./src
COPY server /app/server

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r ./requirements.txt

<<<<<<< HEAD
# Setup startup scripts
RUN mkdir -p /app/data /app/logs /app/output && \
    chmod +x /app/src/scripts/start_http_ui.sh 2>/dev/null || true
=======
<<<<<<< Updated upstream
RUN sed -i 's/\r$//' /app/src/scripts/start_http_ui.sh 2>/dev/null || true && \
    chmod +x /app/src/scripts/start_http_ui.sh 2>/dev/null || true && \
    mkdir -p /app/data /app/logs /app/output
=======
# Setup startup scripts - fix line endings and make executable
RUN mkdir -p /app/data /app/logs /app/output && \
    sed -i 's/\r$//' /app/src/scripts/start_http_ui.sh && \
    chmod +x /app/src/scripts/start_http_ui.sh
>>>>>>> 4bef926f634c72a86f231ee2b5ab2e56b52111ef

EXPOSE 5900 6080

CMD ["python", "/app/main.py"]
<<<<<<< HEAD
=======
>>>>>>> Stashed changes
>>>>>>> 4bef926f634c72a86f231ee2b5ab2e56b52111ef

