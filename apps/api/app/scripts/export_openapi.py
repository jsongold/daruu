#!/usr/bin/env python3
"""Export OpenAPI schema from FastAPI application.

This script extracts the OpenAPI schema from the FastAPI app and exports it
to a JSON file for contract testing and client generation.

Usage:
    python -m app.scripts.export_openapi
    python -m app.scripts.export_openapi --output ../contracts/openapi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def get_openapi_schema() -> dict[str, Any]:
    """Get OpenAPI schema from FastAPI application."""
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


def validate_schema(schema: dict[str, Any]) -> list[str]:
    """Validate the OpenAPI schema for completeness.

    Returns:
        List of validation issues found.
    """
    issues: list[str] = []

    # Check required fields
    if "openapi" not in schema:
        issues.append("Missing 'openapi' version field")

    if "info" not in schema:
        issues.append("Missing 'info' section")
    else:
        info = schema["info"]
        if "title" not in info:
            issues.append("Missing 'info.title'")
        if "version" not in info:
            issues.append("Missing 'info.version'")

    if "paths" not in schema:
        issues.append("Missing 'paths' section")
    else:
        paths = schema["paths"]
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    if "responses" not in operation:
                        issues.append(f"Missing responses for {method.upper()} {path}")
                    if "tags" not in operation:
                        issues.append(f"Missing tags for {method.upper()} {path}")

    return issues


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Export OpenAPI schema from FastAPI application")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent.parent / "contracts" / "openapi.json",
        help="Output path for the OpenAPI JSON file",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Validate the schema after export",
    )
    parser.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Check if schema matches existing file (exit 1 if different)",
    )
    args = parser.parse_args()

    try:
        schema = get_openapi_schema()

        if args.check and args.output.exists():
            # Compare with existing file
            with open(args.output, encoding="utf-8") as f:
                existing = json.load(f)

            if schema != existing:
                print(
                    f"ERROR: Schema differs from {args.output}",
                    file=sys.stderr,
                )
                print("Run without --check to update the schema.", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"Schema matches {args.output}")
                sys.exit(0)

        export_schema(args.output)

        if args.validate:
            issues = validate_schema(schema)
            if issues:
                print("\nValidation issues found:", file=sys.stderr)
                for issue in issues:
                    print(f"  - {issue}", file=sys.stderr)
                sys.exit(1)
            else:
                print("Schema validation passed.")

    except ImportError as e:
        print(f"Error: Could not import FastAPI app: {e}", file=sys.stderr)
        print("Make sure you have the API dependencies installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error exporting schema: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
