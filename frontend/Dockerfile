# ── Stage 1: Build the SvelteKit app ──
FROM node:24-slim AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Production dependencies only ──
FROM node:24-slim AS deps

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ── Stage 3: Runtime ──
FROM node:24-slim

ARG VERSION=dev
LABEL org.opencontainers.image.version=$VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends tini curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 10001 synthesis && \
    useradd -u 10001 -g synthesis -s /sbin/nologin -M synthesis

WORKDIR /app

COPY --from=builder /app/build ./build
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/package.json .

ENV PORT=5199
ENV HOST=0.0.0.0
ENV ORIGIN=http://localhost
ENV NODE_ENV=production

USER synthesis
EXPOSE 5199

ENTRYPOINT ["tini", "--"]
CMD ["node", "build"]
