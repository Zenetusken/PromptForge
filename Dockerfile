# Stage 1: Build frontend
FROM node:24-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime
FROM python:3.12-slim
WORKDIR /app

# Install nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend code
COPY backend/ ./backend/
COPY prompts/ ./prompts/

# Frontend static build
COPY --from=frontend-build /app/frontend/build /app/frontend/build

# nginx config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Data directory
RUN mkdir -p /app/data/traces

# Startup script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 80 8001
VOLUME ["/app/data"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
