FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm@10 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/

WORKDIR /app/frontend
RUN pnpm install --frozen-lockfile

WORKDIR /app
COPY . .

WORKDIR /app/frontend
ARG VITE_RAILWAY_API_URL
ENV VITE_RAILWAY_API_URL=$VITE_RAILWAY_API_URL
RUN pnpm run build

WORKDIR /app

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
