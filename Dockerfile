# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SANDBOX_PROVIDER=auto \
    PORT=8008

WORKDIR /app

# Install minimal OS dependencies for build & health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies first for layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application code and sample datasets
COPY backend/ ./backend/
COPY sample-data/ ./sample-data/

# Ensure runtime directories exist
RUN mkdir -p /app/backend/data/uploads

# Expose standard port
EXPOSE 8008

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8008}/api/health || exit 1

# Start uvicorn dynamically binding to $PORT provided by host (e.g. Railway/Render) or default 8008
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8008}"]
