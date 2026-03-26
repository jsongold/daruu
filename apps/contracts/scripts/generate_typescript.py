#!/usr/bin/env python3
"""Generate TypeScript types from OpenAPI specification.

This script reads the OpenAPI specification (either from FastAPI or YAML file)
and generates TypeScript type definitions.

Usage:
    python scripts/generate_typescript.py
    python scripts/generate_typescript.py --source yaml --output ../../web/src/lib/api-types.ts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def indent(text: str, level: int = 1) -> str:
    """Indent text by specified number of levels (2 spaces each)."""
    prefix = "  " * level
    return "\n".join(prefix + line if line else line for line in text.split("\n"))


def schema_ref_to_type_name(ref: str) -> str:
    """Convert a $ref to a TypeScript type name."""
    # Handle #/components/schemas/TypeName
    if ref.startswith("#/components/schemas/"):
        return ref.split("/")[-1]
    # Handle simple refs
    return ref.split("/")[-1]


def json_type_to_ts(json_type: str | list[str]) -> str:
    """Convert JSON schema type to TypeScript type."""
    type_map = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "object": "Record<string, unknown>",
        "array": "unknown[]",
        "null": "null",
    }

    if isinstance(json_type, list):
        # Handle multiple types like ["string", "null"]
        ts_types = [type_map.get(t, "unknown") for t in json_type]
        return " | ".join(ts_types)

    return type_map.get(json_type, "unknown")


def format_to_ts(format_type: str | None) -> str | None:
    """Convert JSON schema format to TypeScript type."""
    format_map = {
        "date-time": "string",  # ISO 8601 date-time as string
        "date": "string",
        "time": "string",
        "email": "string",
        "uri": "string",
        "uuid": "string",
        "binary": "Blob",
    }
    return format_map.get(format_type or "") if format_type else None


def schema_to_ts_type(
    schema: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
    depth: int = 0,
) -> str:
    """Convert a JSON schema to TypeScript type."""
    if depth > 10:
        return "unknown"

    # Handle $ref
    if "$ref" in schema:
        return schema_ref_to_type_name(schema["$ref"])

    # Handle oneOf/anyOf
    if "oneOf" in schema:
        types = [schema_to_ts_type(s, schemas, depth + 1) for s in schema["oneOf"]]
        return " | ".join(types)

    if "anyOf" in schema:
        types = [schema_to_ts_type(s, schemas, depth + 1) for s in schema["anyOf"]]
        return " | ".join(types)

    # Handle allOf (intersection type)
    if "allOf" in schema:
        types = [schema_to_ts_type(s, schemas, depth + 1) for s in schema["allOf"]]
        return " & ".join(types)

    # Handle enum
    if "enum" in schema:
        return " | ".join(f'"{v}"' for v in schema["enum"])

    # Handle const
    if "const" in schema:
        value = schema["const"]
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    # Handle format
    json_type = schema.get("type", "unknown")
    if json_type == "string" and "format" in schema:
        ts_type = format_to_ts(schema["format"])
        if ts_type:
            return ts_type

    # Handle array
    if json_type == "array":
        items = schema.get("items", {})
        item_type = schema_to_ts_type(items, schemas, depth + 1)
        return f"{item_type}[]"

    # Handle object
    if json_type == "object":
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        additional = schema.get("additionalProperties", True)

        if not properties:
            if additional is True:
                return "Record<string, unknown>"
            elif isinstance(additional, dict):
                val_type = schema_to_ts_type(additional, schemas, depth + 1)
                return f"Record<string, {val_type}>"
            return "Record<string, never>"

        lines = ["{"]
        for prop_name, prop_schema in properties.items():
            prop_type = schema_to_ts_type(prop_schema, schemas, depth + 1)
            optional = "" if prop_name in required else "?"
            description = prop_schema.get("description", "")
            if description:
                lines.append(f"  /** {description} */")
            lines.append(f"  {prop_name}{optional}: {prop_type};")
        lines.append("}")
        return "\n".join(lines)

    # Handle basic types
    return json_type_to_ts(json_type)


def generate_interface(
    name: str,
    schema: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
) -> str:
    """Generate a TypeScript interface from a schema."""
    lines = []

    # Add JSDoc comment
    description = schema.get("description", "")
    if description:
        lines.append(f"/** {description} */")

    ts_type = schema_to_ts_type(schema, schemas)

    # If it's a simple type or union, use type alias
    if not ts_type.startswith("{"):
        lines.append(f"export type {name} = {ts_type};")
    else:
        # It's an object, use interface
        lines.append(f"export interface {name} {ts_type}")

    return "\n".join(lines)


def generate_enum(name: str, values: list[str], description: str = "") -> str:
    """Generate a TypeScript enum from values."""
    lines = []

    if description:
        lines.append(f"/** {description} */")

    lines.append(f"export type {name} =")
    value_lines = [f'  | "{v}"' for v in values]
    lines.extend(value_lines)
    lines[-1] += ";"

    return "\n".join(lines)


def generate_types_from_openapi(spec: dict[str, Any]) -> str:
    """Generate TypeScript types from OpenAPI specification."""
    lines = [
        "/**",
        " * Auto-generated TypeScript types from OpenAPI specification.",
        " * DO NOT EDIT MANUALLY - regenerate using scripts/generate_typescript.py",
        " *",
        f" * Generated from: {spec.get('info', {}).get('title', 'Unknown API')}",
        f" * Version: {spec.get('info', {}).get('version', 'unknown')}",
        " */",
        "",
        "/* eslint-disable @typescript-eslint/no-explicit-any */",
        "",
    ]

    schemas = spec.get("components", {}).get("schemas", {})

    # Sort schemas alphabetically for consistent output
    for name in sorted(schemas.keys()):
        schema = schemas[name]
        interface_code = generate_interface(name, schema, schemas)
        lines.append(interface_code)
        lines.append("")

    # Add API response wrapper types
    lines.extend(
        [
            "// API Response Wrappers",
            "",
            "export interface ApiResponse<T> {",
            "  success: boolean;",
            "  data?: T;",
            "  error?: string;",
            "  meta?: Record<string, unknown>;",
            "}",
            "",
            "export interface ApiErrorResponse {",
            "  success: false;",
            "  error: {",
            "    code: string;",
            "    message: string;",
            "    field?: string;",
            "    trace_id?: string;",
            "  };",
            "}",
            "",
            "// Request/Response type helpers",
            "",
            "export type DocumentUploadRequest = FormData;",
            "",
            "export type CreateJobRequest = JobCreateRequest;",
            "export type CreateJobResponse = ApiResponse<{ job_id: string }>;",
            "",
            "export type GetJobResponse = ApiResponse<JobContext>;",
            "export type RunJobResponse = ApiResponse<JobRunResponse>;",
            "",
        ]
    )

    return "\n".join(lines)


def load_openapi_from_yaml(path: Path) -> dict[str, Any]:
    """Load OpenAPI spec from YAML file."""
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_openapi_from_fastapi() -> dict[str, Any]:
    """Load OpenAPI spec from FastAPI application."""
    api_path = Path(__file__).parent.parent.parent / "api"
    sys.path.insert(0, str(api_path))

    from app.main import app

    return app.openapi()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate TypeScript types from OpenAPI specification"
    )
    parser.add_argument(
        "--source",
        choices=["fastapi", "yaml"],
        default="yaml",
        help="Source of OpenAPI spec (default: yaml)",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path(__file__).parent.parent / "openapi" / "api.yaml",
        help="Input YAML file (when source=yaml)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent.parent.parent / "web" / "src" / "lib" / "api-types.ts",
        help="Output TypeScript file",
    )
    args = parser.parse_args()

    try:
        # Load OpenAPI spec
        if args.source == "yaml":
            spec = load_openapi_from_yaml(args.input)
        else:
            spec = load_openapi_from_fastapi()

        # Generate TypeScript types
        ts_code = generate_types_from_openapi(spec)

        # Ensure output directory exists
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(ts_code)

        print(f"TypeScript types generated: {args.output}")

    except ImportError as e:
        print(f"Error: Could not import required module: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error generating types: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
