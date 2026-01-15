FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

COPY frontend/package.json ./frontend/

WORKDIR /app/frontend
RUN pnpm install --frozen-lockfile

WORKDIR /app
COPY . .

WORKDIR /app/frontend
RUN pnpm run build

WORKDIR /app

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
