# Stage 1: Build wrangler-ui static assets
FROM node:22-slim AS ui-build
WORKDIR /build/wrangler-ui
COPY apps/wrangler-ui/package.json apps/wrangler-ui/package-lock.json ./
RUN npm install
COPY apps/wrangler-ui/ ./
RUN mkdir -p /build/wrangler/static/wrangler-ui
RUN npx vite build --outDir /build/wrangler/static/wrangler-ui --emptyOutDir

# Stage 2: Python app with uv
FROM python:3.13-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy contracts (local dep)
COPY packages/contracts /app/packages/contracts

# Copy wrangler source
COPY apps/wrangler/pyproject.toml /app/apps/wrangler/
COPY apps/wrangler/src /app/apps/wrangler/src

# Install deps
WORKDIR /app/apps/wrangler
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Copy built UI
COPY --from=ui-build /build/wrangler/static/wrangler-ui /app/apps/wrangler/static/wrangler-ui

EXPOSE 8501

CMD ["uv", "run", "wrangler", "serve", "--host", "0.0.0.0", "--port", "8501"]
