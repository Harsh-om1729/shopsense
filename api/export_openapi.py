"""Write the API schema for the frontend, which generates its types from it.

Run after changing the API with: uv run python -m api.export_openapi
"""

import json

from api.main import create_app
from src import config

OPENAPI_PATH = config.PROJECT_ROOT / "frontend" / "openapi.json"


def schema_text() -> str:
    """Return the schema in a stable format, so unchanged APIs give identical files."""
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(schema_text())
    print(f"Saved the API schema to {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
