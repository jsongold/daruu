#!/usr/bin/env python3
"""Export OpenAPI schema from FastAPI application.

This script extracts the OpenAPI schema from the FastAPI app and exports it
to a JSON file for contract testing and client generation.

Usage:
    python scripts/export_openapi.py
    python scripts/export_openapi.py --output ../openapi/openapi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def get_openapi_schema() -> dict:
    """Get OpenAPI schema from FastAPI application."""
    # Add the api app to the path
    api_path = Path(__file__).parent.parent.parent / "api"
    sys.path.insert(0, str(api_path))

    from app.main import app

    return app.openapi()


def export_schema(output_path: Path) -> None:
    """Export OpenAPI schema to a JSON file."""
    schema = get_openapi_schema()

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the schema
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"OpenAPI schema exported to: {output_path}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export OpenAPI schema from FastAPI application"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent / "openapi" / "openapi.json",
        help="Output path for the OpenAPI JSON file",
    )
    args = parser.parse_args()

    try:
        export_schema(args.output)
    except ImportError as e:
        print(f"Error: Could not import FastAPI app: {e}", file=sys.stderr)
        print("Make sure you have the API dependencies installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error exporting schema: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
