# syntax=docker/dockerfile:1

# Stage 1: Build the React 19 frontend
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.12-slim

WORKDIR /app

# Install minimal system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copy backend application code and official data records
COPY backend/app ./app
COPY backend/data ./data
COPY backend/pyproject.toml ./

# Copy built frontend SPA from builder stage
COPY --from=frontend-builder /app/frontend/dist /app/frontend_dist

# Ensure runtime storage directory exists
RUN mkdir -p /app/storage

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    FRONTEND_DIR=/app/frontend_dist \
    DATA_DIR=/app/storage \
    PORT=8000

EXPOSE 8000

# Bind Uvicorn to 0.0.0.0 and the dynamic port provided by Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
