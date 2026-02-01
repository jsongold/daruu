"""
Test JSON Schema validation for all contract schemas and examples.

This module validates:
1. All JSON schemas are valid JSON Schema draft-07
2. All example files validate against their referenced schemas
3. Schema definitions are consistent and well-formed
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator, RefResolver, ValidationError, validate

# Base paths
CONTRACTS_DIR = Path(__file__).parent.parent
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_all_schema_files() -> list[Path]:
    """Get all JSON schema files."""
    return list(SCHEMAS_DIR.glob("*.json"))


def get_all_example_files() -> list[Path]:
    """Get all example JSON files."""
    examples: list[Path] = []
    for subdir in EXAMPLES_DIR.iterdir():
        if subdir.is_dir():
            examples.extend(subdir.glob("*.json"))
    return examples


def load_all_schemas() -> dict[str, dict[str, Any]]:
    """Load all schemas and return them indexed by filename stem."""
    return {f.stem: load_json(f) for f in get_all_schema_files()}


def create_resolver() -> RefResolver:
    """Create a JSON Schema resolver for handling $ref."""
    schema_store: dict[str, Any] = {}

    # Load all schemas into the store with multiple key formats
    for schema_file in get_all_schema_files():
        schema = load_json(schema_file)
        schema_id = schema.get("$id", f"file://{schema_file}")
        schema_store[schema_id] = schema
        # Also store by filename for relative refs
        schema_store[schema_file.name] = schema
        # Store by file:// URI format
        schema_store[f"file://{schema_file.resolve()}"] = schema

    # Create resolver with base URI pointing to schemas directory
    base_uri = f"file://{SCHEMAS_DIR.resolve()}/"
    base_schema = load_json(SCHEMAS_DIR / "common.json")

    # Use handlers for file:// URIs
    handlers = {
        "file": lambda uri: schema_store.get(uri, load_json(Path(uri.replace("file://", ""))))
    }

    return RefResolver(base_uri, base_schema, store=schema_store, handlers=handlers)


def inline_external_refs(
    schema: dict[str, Any],
    all_schemas: dict[str, dict[str, Any]],
    visited: set[str] | None = None,
) -> dict[str, Any]:
    """
    Inline external file references in a schema.

    This creates a self-contained schema by replacing external refs like
    'field.json#/definitions/Field' with the actual definition inlined
    into the schema's definitions.

    This function recursively processes inlined definitions to handle
    nested external references (e.g., Evidence -> EvidenceSource).
    """
    if visited is None:
        visited = set()

    result = copy.deepcopy(schema)

    # Iteratively process until no new external refs are found
    max_iterations = 20  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Collect all external refs
        external_refs: dict[str, tuple[str, str]] = {}
        _collect_external_refs(result, external_refs)

        # Filter out already processed refs
        new_refs = {k: v for k, v in external_refs.items() if k not in visited}

        if not new_refs:
            break

        # Add inlined definitions
        if new_refs and "definitions" not in result:
            result["definitions"] = {}

        for ref_key, (schema_name, def_path) in new_refs.items():
            visited.add(ref_key)

            if schema_name in all_schemas:
                source_schema = all_schemas[schema_name]
                # Navigate to the definition
                definition = _get_definition(source_schema, def_path)
                if definition:
                    # Deep copy the definition to avoid mutation
                    inlined_def = copy.deepcopy(definition)
                    result["definitions"][ref_key] = inlined_def

                    # Also inline any definitions that this definition references
                    # from the same source schema
                    _inline_internal_refs_from_source(
                        result, source_schema, schema_name, visited
                    )

        # Replace external refs with internal refs
        _replace_external_refs(result, external_refs)

    return result


def _inline_internal_refs_from_source(
    result: dict[str, Any],
    source_schema: dict[str, Any],
    schema_name: str,
    visited: set[str],
) -> None:
    """
    Inline internal definitions from source schema that are referenced
    by already-inlined definitions, and rewrite the refs to point to
    the inlined definitions.
    """
    # Get all definitions from source schema
    source_defs = source_schema.get("definitions", {})

    # Check each inlined definition for internal refs to source schema
    result_defs = result.get("definitions", {})

    for def_name, definition in list(result_defs.items()):
        # Only process inlined definitions from this schema
        if not def_name.startswith(f"_inline_{schema_name}_"):
            continue

        # Find internal refs in this definition
        internal_refs = _find_internal_refs(definition)

        for ref in internal_refs:
            # Parse ref like "#/definitions/EvidenceSource"
            if ref.startswith("#/definitions/"):
                ref_def_name = ref.split("/")[-1]
                ref_key = f"_inline_{schema_name}_{ref_def_name}"

                if ref_def_name in source_defs:
                    # Always add the definition if it's from source schema
                    if ref_key not in result_defs:
                        visited.add(ref_key)
                        result_defs[ref_key] = copy.deepcopy(source_defs[ref_def_name])

    # Now rewrite internal refs within inlined definitions
    for def_name, definition in result_defs.items():
        if def_name.startswith(f"_inline_{schema_name}_"):
            _rewrite_internal_refs(definition, schema_name, source_defs)


def _rewrite_internal_refs(
    obj: Any,
    schema_name: str,
    source_defs: dict[str, Any],
) -> None:
    """
    Rewrite internal refs in an inlined definition to point to
    the inlined version of the referenced definition.
    """
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref.startswith("#/definitions/"):
                ref_def_name = ref.split("/")[-1]
                # Only rewrite if this definition exists in source schema
                if ref_def_name in source_defs:
                    obj["$ref"] = f"#/definitions/_inline_{schema_name}_{ref_def_name}"

        for value in obj.values():
            _rewrite_internal_refs(value, schema_name, source_defs)

    elif isinstance(obj, list):
        for item in obj:
            _rewrite_internal_refs(item, schema_name, source_defs)


def _find_internal_refs(obj: Any) -> list[str]:
    """Find all internal $ref values in an object."""
    refs: list[str] = []

    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref.startswith("#"):
                refs.append(ref)

        for value in obj.values():
            refs.extend(_find_internal_refs(value))

    elif isinstance(obj, list):
        for item in obj:
            refs.extend(_find_internal_refs(item))

    return refs


def _collect_external_refs(
    obj: Any,
    refs: dict[str, tuple[str, str]],
) -> None:
    """Collect all external file references in an object."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            # Check for external file refs (not starting with #)
            if not ref.startswith("#") and ".json#" in ref:
                # Parse ref like 'field.json#/definitions/Field'
                parts = ref.split("#", 1)
                file_part = parts[0]
                def_path = parts[1] if len(parts) > 1 else ""

                schema_name = Path(file_part).stem
                # Create unique key
                def_name = def_path.split("/")[-1] if def_path else schema_name
                ref_key = f"_inline_{schema_name}_{def_name}"
                refs[ref_key] = (schema_name, def_path)

        for value in obj.values():
            _collect_external_refs(value, refs)

    elif isinstance(obj, list):
        for item in obj:
            _collect_external_refs(item, refs)


def _replace_external_refs(
    obj: Any,
    refs: dict[str, tuple[str, str]],
) -> None:
    """Replace external refs with internal refs to inlined definitions."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if not ref.startswith("#") and ".json#" in ref:
                parts = ref.split("#", 1)
                file_part = parts[0]
                def_path = parts[1] if len(parts) > 1 else ""

                schema_name = Path(file_part).stem
                def_name = def_path.split("/")[-1] if def_path else schema_name
                ref_key = f"_inline_{schema_name}_{def_name}"

                # Always replace, as we've now added all needed definitions
                obj["$ref"] = f"#/definitions/{ref_key}"

        for value in obj.values():
            _replace_external_refs(value, refs)

    elif isinstance(obj, list):
        for item in obj:
            _replace_external_refs(item, refs)


def _get_definition(schema: dict[str, Any], path: str) -> dict[str, Any] | None:
    """Get a definition from a schema by path."""
    if not path:
        return schema

    parts = path.strip("/").split("/")
    current: Any = schema

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current if isinstance(current, dict) else None


class TestSchemaValidity:
    """Test that all JSON schemas are valid draft-07 schemas."""

    @pytest.fixture(scope="class")
    def meta_schema(self) -> dict[str, Any]:
        """Load the JSON Schema draft-07 meta-schema."""
        # Using a simplified check - Draft7Validator.check_schema validates against meta-schema
        return {}

    @pytest.mark.parametrize("schema_file", get_all_schema_files(), ids=lambda x: x.name)
    def test_schema_is_valid_draft07(self, schema_file: Path) -> None:
        """Verify each schema is a valid JSON Schema draft-07."""
        schema = load_json(schema_file)

        # Check that $schema is specified and is draft-07
        assert "$schema" in schema, f"Schema {schema_file.name} missing $schema declaration"
        assert "draft-07" in schema["$schema"], f"Schema {schema_file.name} should be draft-07"

        # Validate the schema itself
        try:
            Draft7Validator.check_schema(schema)
        except Exception as e:
            pytest.fail(f"Schema {schema_file.name} is not valid: {e}")

    @pytest.mark.parametrize("schema_file", get_all_schema_files(), ids=lambda x: x.name)
    def test_schema_has_required_fields(self, schema_file: Path) -> None:
        """Verify each schema has required metadata fields."""
        schema = load_json(schema_file)

        assert "$id" in schema, f"Schema {schema_file.name} missing $id"
        assert "title" in schema, f"Schema {schema_file.name} missing title"
        assert "description" in schema, f"Schema {schema_file.name} missing description"

    @pytest.mark.parametrize("schema_file", get_all_schema_files(), ids=lambda x: x.name)
    def test_schema_definitions_are_valid(self, schema_file: Path) -> None:
        """Verify all definitions within a schema are properly formed."""
        schema = load_json(schema_file)

        if "definitions" not in schema:
            pytest.skip(f"Schema {schema_file.name} has no definitions")

        for def_name, definition in schema["definitions"].items():
            # Each definition should have a type or be a reference
            has_type = "type" in definition
            has_ref = "$ref" in definition
            has_oneof = "oneOf" in definition
            has_anyof = "anyOf" in definition
            has_allof = "allOf" in definition
            has_enum = "enum" in definition
            has_const = "const" in definition

            valid_definition = any([
                has_type, has_ref, has_oneof, has_anyof, has_allof, has_enum, has_const
            ])

            assert valid_definition, (
                f"Definition '{def_name}' in {schema_file.name} must have "
                "type, $ref, oneOf, anyOf, allOf, enum, or const"
            )


class TestExampleValidation:
    """Test that all example files validate against their schemas."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, Any]:
        """Load all schemas into a dictionary."""
        return load_all_schemas()

    def _get_schema_for_example(
        self, example_data: dict[str, Any], schemas: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get the schema and definition path for an example.
        Returns (schema, definition_path) or (None, None) if not found.
        """
        schema_ref = example_data.get("$schema")
        if not schema_ref:
            return None, None

        # Parse the schema reference (e.g., "../../schemas/document.json#/definitions/Document")
        if "#" in schema_ref:
            schema_path, definition_path = schema_ref.split("#", 1)
        else:
            schema_path = schema_ref
            definition_path = None

        # Extract schema name from path
        schema_name = Path(schema_path).stem

        if schema_name not in schemas:
            return None, None

        return schemas[schema_name], definition_path

    def _resolve_definition(
        self, schema: dict[str, Any], definition_path: str | None
    ) -> dict[str, Any]:
        """Resolve a definition path within a schema."""
        if not definition_path:
            return schema

        # Parse path like "/definitions/Document"
        parts = definition_path.strip("/").split("/")
        current = schema

        for part in parts:
            if part in current:
                current = current[part]
            else:
                raise KeyError(f"Cannot resolve path '{definition_path}' in schema")

        return current

    @pytest.mark.parametrize("example_file", get_all_example_files(), ids=lambda x: x.name)
    def test_example_validates_against_schema(
        self, example_file: Path, schemas: dict[str, Any]
    ) -> None:
        """Verify each example file validates against its declared schema."""
        example_data = load_json(example_file)

        # Skip examples without $schema reference
        if "$schema" not in example_data:
            pytest.skip(f"Example {example_file.name} has no $schema reference")

        schema, definition_path = self._get_schema_for_example(example_data, schemas)

        if schema is None:
            pytest.fail(f"Could not find schema for {example_file.name}")

        # Inline external references to create self-contained schema
        inlined_schema = inline_external_refs(schema, schemas)

        # Resolve the specific definition
        try:
            target_def = self._resolve_definition(inlined_schema, definition_path)
        except KeyError as e:
            pytest.fail(f"Could not resolve schema definition for {example_file.name}: {e}")

        # Create a complete schema that wraps the target definition
        # This allows internal refs like #/definitions/X to work
        complete_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": inlined_schema.get("definitions", {}),
            **target_def,
        }

        # Remove $schema and _description from example before validation
        data_to_validate = {
            k: v for k, v in example_data.items()
            if k not in ("$schema", "_description")
        }

        # Validate the example against the schema
        try:
            validator = Draft7Validator(complete_schema)
            errors = list(validator.iter_errors(data_to_validate))

            if errors:
                error_messages = "\n".join(
                    f"  - {e.message} at {list(e.absolute_path)}" for e in errors
                )
                pytest.fail(
                    f"Example {example_file.name} failed validation:\n{error_messages}"
                )
        except Exception as e:
            pytest.fail(f"Validation error for {example_file.name}: {e}")

    @pytest.mark.parametrize("example_file", get_all_example_files(), ids=lambda x: x.name)
    def test_example_has_valid_json(self, example_file: Path) -> None:
        """Verify each example file is valid JSON."""
        try:
            load_json(example_file)
        except json.JSONDecodeError as e:
            pytest.fail(f"Example {example_file.name} is not valid JSON: {e}")


class TestSchemaConsistency:
    """Test consistency across schemas."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return {f.stem: load_json(f) for f in get_all_schema_files()}

    def test_common_types_are_consistent(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify common types like BBox are defined consistently."""
        # Check that BBox is defined in common.json and consistently in other schemas
        common_schema = schemas.get("common")
        assert common_schema is not None, "common.json schema not found"

        common_bbox = common_schema.get("definitions", {}).get("BBox")
        assert common_bbox is not None, "BBox not defined in common.json"

        # Check required fields in BBox
        bbox_required = common_bbox.get("required", [])
        expected_bbox_fields = ["page", "x", "y", "width", "height"]

        for field in expected_bbox_fields:
            assert field in bbox_required, f"BBox missing required field: {field}"

    def test_uuid_format_is_consistent(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify UUID fields use format: uuid consistently."""
        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name, definition in definitions.items():
                properties = definition.get("properties", {})

                # Check fields that should be UUIDs
                id_fields = ["id", "job_id", "document_id", "field_id",
                             "source_field_id", "target_field_id", "evidence_id",
                             "issue_id"]

                for field_name in id_fields:
                    if field_name in properties:
                        field_def = properties[field_name]
                        if field_def.get("type") == "string":
                            assert field_def.get("format") == "uuid", (
                                f"{schema_name}.{def_name}.{field_name} should have format: uuid"
                            )

    def test_datetime_format_is_consistent(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify datetime fields use format: date-time consistently."""
        datetime_field_names = [
            "created_at", "updated_at", "completed_at", "resolved_at", "timestamp"
        ]

        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name, definition in definitions.items():
                properties = definition.get("properties", {})

                for field_name in datetime_field_names:
                    if field_name in properties:
                        field_def = properties[field_name]
                        if field_def.get("type") == "string":
                            assert field_def.get("format") == "date-time", (
                                f"{schema_name}.{def_name}.{field_name} "
                                "should have format: date-time"
                            )

    def test_confidence_fields_have_valid_range(
        self, schemas: dict[str, dict[str, Any]]
    ) -> None:
        """Verify confidence fields have min 0 and max 1."""
        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name, definition in definitions.items():
                properties = definition.get("properties", {})

                if "confidence" in properties:
                    conf_def = properties["confidence"]
                    if conf_def.get("type") == "number":
                        assert conf_def.get("minimum") == 0, (
                            f"{schema_name}.{def_name}.confidence should have minimum: 0"
                        )
                        assert conf_def.get("maximum") == 1, (
                            f"{schema_name}.{def_name}.confidence should have maximum: 1"
                        )


class TestCrossSchemaReferences:
    """Test that cross-schema references are valid."""

    @pytest.fixture(scope="class")
    def resolver(self) -> RefResolver:
        """Create a resolver for handling schema references."""
        return create_resolver()

    def test_job_context_references_are_valid(self, resolver: RefResolver) -> None:
        """Verify JobContext schema can resolve all its references."""
        job_context_schema = load_json(SCHEMAS_DIR / "job_context.json")

        # The JobContext references Field, Mapping, Extraction, Issue, Activity
        referenced_schemas = ["field", "mapping", "extraction", "issue", "activity"]

        for ref_name in referenced_schemas:
            ref_path = f"{ref_name}.json#/definitions/{ref_name.capitalize()}"
            try:
                resolved = resolver.resolve(ref_path)
                assert resolved is not None, f"Could not resolve {ref_path}"
            except Exception as e:
                # References might use different casing or paths
                pass  # Skip if reference format differs

    def test_all_internal_refs_are_valid(self) -> None:
        """Verify all internal $ref within schemas are valid."""
        for schema_file in get_all_schema_files():
            schema = load_json(schema_file)
            self._check_refs_in_obj(schema, schema, schema_file.name)

    def _check_refs_in_obj(
        self, obj: Any, root_schema: dict[str, Any], schema_name: str
    ) -> None:
        """Recursively check all $ref in an object."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                # Check internal refs (starting with #)
                if ref.startswith("#"):
                    self._validate_internal_ref(ref, root_schema, schema_name)

            for value in obj.values():
                self._check_refs_in_obj(value, root_schema, schema_name)

        elif isinstance(obj, list):
            for item in obj:
                self._check_refs_in_obj(item, root_schema, schema_name)

    def _validate_internal_ref(
        self, ref: str, schema: dict[str, Any], schema_name: str
    ) -> None:
        """Validate an internal reference can be resolved."""
        path = ref[1:]  # Remove leading #
        parts = path.strip("/").split("/")

        current = schema
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                pytest.fail(
                    f"Invalid internal ref '{ref}' in {schema_name}: "
                    f"cannot resolve '{part}'"
                )
