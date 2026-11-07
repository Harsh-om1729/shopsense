# ShopSense: the API and website in one image.
#
# Code only. Trained models and the database aren't in git and aren't copied
# in. docker-compose.yml attaches them from your folders at run time.

# Stage 1: build the website into static files.
FROM node:24-slim AS site
WORKDIR /site
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python app, which serves the API and the built site.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /bin/uv

# No bytecode pre-compiling, which would add hundreds of MB for a small startup gain.
ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    SHOPSENSE_STATIC_DIR=/app/frontend/dist

WORKDIR /app
# Install dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ src/
COPY api/ api/
COPY reports/ reports/
COPY --from=site /site/dist frontend/dist

RUN useradd --create-home shopsense \
    && mkdir -p models data/processed \
    && chown -R shopsense /app
USER shopsense

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["uvicorn", "api.serve:app", "--host", "0.0.0.0", "--port", "8000"]
