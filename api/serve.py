"""Serve the built website and the API from one address, for production.

In development, Vite serves the site and forwards /api to FastAPI. Here,
FastAPI does both: the API lives under /api and the site under /. Because both
share one address, the browser needs no CORS settings.

Run with: SHOPSENSE_STATIC_DIR=frontend/dist uv run uvicorn api.serve:app
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from api.main import create_app
from src import config

DEFAULT_STATIC_DIR = config.PROJECT_ROOT / "frontend" / "dist"


class SiteFiles(StaticFiles):
    """Serve the site, sending unknown paths to index.html.

    The site handles its own pages, so refreshing /reviews must return the app
    rather than a 404.
    """

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def create_production_app(static_dir: Path | None = None, api: FastAPI | None = None) -> FastAPI:
    """Return an app with the API under /api and the site at /."""
    static_dir = Path(static_dir or os.environ.get("SHOPSENSE_STATIC_DIR", DEFAULT_STATIC_DIR))
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"No built site in {static_dir}. Run: cd frontend && npm run build")
    api = api or create_app()

    # A mounted app's startup doesn't run by itself, so the parent runs it.
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with api.router.lifespan_context(api):
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/api", api)
    app.mount("/", SiteFiles(directory=static_dir, html=True), name="site")
    return app


def __getattr__(name: str):
    # Build the app only when uvicorn asks for it, so importing this module in
    # tests doesn't need a built site.
    if name == "app":
        return create_production_app()
    raise AttributeError(name)
