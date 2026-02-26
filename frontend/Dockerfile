# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Build args for Vite (embedded at build time via import.meta.env)
ARG VITE_API_URL

# Copy dependency files first for layer caching
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build (VITE_* args are available as env vars)
COPY . .
RUN npm run build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

# Copy built output and install only production deps
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
COPY --from=build /app/package-lock.json* ./
RUN npm ci --omit=dev

# Create non-root user
RUN adduser -D -s /bin/false appuser
USER appuser

EXPOSE 5199

ENV PORT=5199
ENV HOST=0.0.0.0
ENV ORIGIN=http://localhost:5199

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:5199/ || exit 1

CMD ["node", "build"]
