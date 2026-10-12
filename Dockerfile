FROM python:3.11-slim

# LibreOffice (writer + impress, sans interface) : DOCX, PPTX, ODT, RTF convertis en PDF pour que
# les citations s'ouvrent à la page (backend/document_processor/formats.py).
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    && apt-get install -y --no-install-recommends \
    libreoffice-writer-nogui \
    libreoffice-impress-nogui \
    fonts-dejavu \
    fonts-liberation \
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
RUN pnpm run build

WORKDIR /app

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Migrations, puis gunicorn. L'ingestion des documents tourne dans ces processus (boucle de fond,
# backend/saas/ingestion.py) : les originaux sont sur le volume Railway monté sur CE service.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn backend.wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 8 --timeout 300"]
