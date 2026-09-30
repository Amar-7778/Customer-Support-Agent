# Multi-stage Dockerfile for Novintix Support Intelligence Platform

# --- Stage 1: Build React Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python Backend Runtime ---
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source, config, data
COPY src/ ./src/
COPY config/ ./config/
COPY data/ ./data/

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose API port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Start FastAPI application
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
