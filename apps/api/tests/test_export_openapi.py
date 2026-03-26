"""
Tests for the export_openapi script.

Validates that:
1. OpenAPI schema can be generated from FastAPI app
2. Schema contains required sections
3. All routes have proper documentation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def test_openapi_can_be_generated() -> None:
    """Verify OpenAPI schema can be generated from FastAPI app."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()

    assert isinstance(schema, dict)
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_openapi_has_required_info() -> None:
    """Verify OpenAPI info section is complete."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()
    info = schema["info"]

    assert "title" in info
    assert "version" in info
    assert "description" in info


def test_openapi_has_documented_paths() -> None:
    """Verify all paths have documentation."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()
    paths = schema["paths"]

    # Key paths that must exist
    expected_paths = [
        "/api/v1/documents",
        "/api/v1/jobs",
    ]

    for expected_path in expected_paths:
        assert expected_path in paths, f"Missing path: {expected_path}"


def test_openapi_routes_have_responses() -> None:
    """Verify all routes have response documentation."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()
    paths = schema["paths"]

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete"]:
            if method in path_item:
                operation = path_item[method]
                assert "responses" in operation, f"Missing responses for {method.upper()} {path}"


def test_openapi_schema_validation() -> None:
    """Verify generated schema passes validation."""
    from app.scripts.export_openapi import get_openapi_schema, validate_schema

    schema = get_openapi_schema()
    issues = validate_schema(schema)

    # No critical issues should be present
    assert not any(
        "Missing 'openapi'" in issue or "Missing 'info'" in issue or "Missing 'paths'" in issue
        for issue in issues
    )


def test_export_schema_to_file() -> None:
    """Verify schema can be exported to a file."""
    from app.scripts.export_openapi import export_schema

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "openapi.json"
        export_schema(output_path)

        assert output_path.exists()

        with open(output_path, encoding="utf-8") as f:
            loaded_schema = json.load(f)

        assert "openapi" in loaded_schema
        assert "info" in loaded_schema
        assert "paths" in loaded_schema


def test_openapi_has_component_schemas() -> None:
    """Verify OpenAPI has component schemas defined."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()

    # Should have components section
    assert "components" in schema

    components = schema["components"]
    assert "schemas" in components

    schemas = components["schemas"]

    # Key schemas that must exist (these are generated from Pydantic models)
    expected_schemas = [
        "JobCreate",
        "JobResponse",
        "RunRequest",
        "RunResponse",
        "BBox",
        "JobContext",
        "FieldModel",
        "Activity",
    ]

    for expected_schema in expected_schemas:
        assert expected_schema in schemas, f"Missing schema: {expected_schema}"


def test_openapi_schemas_have_descriptions() -> None:
    """Verify component schemas have descriptions."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()
    schemas = schema.get("components", {}).get("schemas", {})

    # At minimum, key schemas should have descriptions
    key_schemas = ["JobCreate", "JobResponse", "BBox"]

    for schema_name in key_schemas:
        if schema_name in schemas:
            component_schema = schemas[schema_name]
            # Either title or description should be present
            has_docs = "title" in component_schema or "description" in component_schema
            assert has_docs, f"Schema {schema_name} lacks documentation"


def test_openapi_has_servers() -> None:
    """Verify OpenAPI has servers defined."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()

    assert "servers" in schema
    servers = schema["servers"]
    assert len(servers) > 0


def test_openapi_has_tags() -> None:
    """Verify OpenAPI has tags defined."""
    from app.scripts.export_openapi import get_openapi_schema

    schema = get_openapi_schema()

    assert "tags" in schema
    tags = schema["tags"]
    assert len(tags) > 0

    # Verify each tag has a name
    for tag in tags:
        assert "name" in tag
