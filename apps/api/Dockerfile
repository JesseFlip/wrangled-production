# Stage 1: Build dashboard static assets
FROM node:22-slim AS dashboard-build
WORKDIR /build
COPY apps/dashboard/package.json apps/dashboard/package-lock.json apps/dashboard/
RUN cd apps/dashboard && npm install --legacy-peer-deps
COPY apps/dashboard/ apps/dashboard/
RUN mkdir -p apps/api/static/dashboard && \
    cd apps/dashboard && npx vite build --outDir ../api/static/dashboard --emptyOutDir

# Stage 2: Python app with uv
FROM python:3.13-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy all Python packages (contracts + wrangler as source deps + api)
COPY packages/contracts /app/packages/contracts
COPY apps/wrangler/pyproject.toml /app/apps/wrangler/pyproject.toml
COPY apps/wrangler/src /app/apps/wrangler/src
COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY apps/api/src /app/apps/api/src

# Install deps
WORKDIR /app/apps/api
RUN uv sync --no-dev

# Copy built dashboard
COPY --from=dashboard-build /build/apps/api/static/dashboard /app/apps/api/static/dashboard

EXPOSE 8500

CMD ["uv", "run", "api", "serve", "--host", "0.0.0.0", "--port", "8500"]
