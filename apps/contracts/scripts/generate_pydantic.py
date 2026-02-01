#!/usr/bin/env python3
"""
Generate Pydantic models from JSON Schema definitions.

This script uses datamodel-code-generator to generate Pydantic v2 models
from the JSON Schema files in the schemas/ directory.

Usage:
    python scripts/generate_pydantic.py [--output-dir OUTPUT_DIR]

Example:
    python scripts/generate_pydantic.py --output-dir ../api/app/models/generated
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# Base paths
SCRIPT_DIR = Path(__file__).parent
CONTRACTS_DIR = SCRIPT_DIR.parent
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
DEFAULT_OUTPUT_DIR = CONTRACTS_DIR / "generated"


def get_schema_files() -> list[Path]:
    """Get all JSON schema files in order of dependencies."""
    # Order matters: common first, then models that don't reference others,
    # then models that reference others
    schema_order = [
        "common.json",
        "document.json",
        "field.json",
        "mapping.json",
        "evidence.json",
        "extraction.json",
        "activity.json",
        "issue.json",
        "job_context.json",
    ]

    files = []
    for schema_name in schema_order:
        schema_path = SCHEMAS_DIR / schema_name
        if schema_path.exists():
            files.append(schema_path)

    return files


def generate_models_for_schema(
    schema_path: Path,
    output_dir: Path,
    use_union_operator: bool = True,
) -> bool:
    """
    Generate Pydantic models for a single schema file.

    Args:
        schema_path: Path to the JSON Schema file
        output_dir: Directory to output generated models
        use_union_operator: Whether to use Python 3.10+ union operator

    Returns:
        True if generation succeeded, False otherwise
    """
    output_file = output_dir / f"{schema_path.stem}.py"

    cmd = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(schema_path),
        "--output",
        str(output_file),
        "--input-file-type",
        "jsonschema",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--use-schema-description",
        "--use-field-description",
        "--use-default",
        "--use-default-kwarg",
        "--strict-nullable",
        "--field-constraints",
        "--collapse-root-models",
        "--use-double-quotes",
        "--target-python-version",
        "3.11",
    ]

    if use_union_operator:
        cmd.append("--use-union-operator")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"Error generating {schema_path.name}:")
            print(result.stderr)
            return False

        print(f"Generated: {output_file.relative_to(CONTRACTS_DIR)}")
        return True

    except Exception as e:
        print(f"Exception generating {schema_path.name}: {e}")
        return False


def generate_all_models(output_dir: Path) -> bool:
    """
    Generate Pydantic models for all schemas.

    Args:
        output_dir: Directory to output generated models

    Returns:
        True if all generations succeeded, False otherwise
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    init_file = output_dir / "__init__.py"
    init_content = '''"""
Auto-generated Pydantic models from JSON Schema definitions.

DO NOT EDIT MANUALLY - regenerate with:
    python scripts/generate_pydantic.py

Models are generated from the schemas/ directory.
"""

from .common import *
from .document import *
from .field import *
from .mapping import *
from .evidence import *
from .extraction import *
from .activity import *
from .issue import *
from .job_context import *
'''
    init_file.write_text(init_content)
    print(f"Generated: {init_file.relative_to(CONTRACTS_DIR)}")

    # Generate models for each schema
    schema_files = get_schema_files()
    success = True

    for schema_file in schema_files:
        if not generate_models_for_schema(schema_file, output_dir):
            success = False

    return success


def generate_combined_model(output_dir: Path) -> bool:
    """
    Generate a single combined model file from all schemas.

    This creates a single file with all models properly ordered
    to handle cross-references.

    Args:
        output_dir: Directory to output combined model

    Returns:
        True if generation succeeded, False otherwise
    """
    combined_output = output_dir / "models.py"

    # First generate individual files
    temp_dir = output_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    schema_files = get_schema_files()

    for schema_file in schema_files:
        generate_models_for_schema(schema_file, temp_dir, use_union_operator=True)

    # Combine into single file
    header = '''"""
Combined Pydantic models from JSON Schema definitions.

DO NOT EDIT MANUALLY - regenerate with:
    python scripts/generate_pydantic.py --combined

Models are generated from the schemas/ directory.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


'''

    combined_content = [header]
    seen_classes: set[str] = set()
    seen_imports: set[str] = set()

    for schema_file in schema_files:
        model_file = temp_dir / f"{schema_file.stem}.py"
        if model_file.exists():
            content = model_file.read_text()

            # Extract and skip duplicate imports
            lines = content.split("\n")
            filtered_lines = []

            for line in lines:
                # Skip imports (we handle them in header)
                if line.startswith("from ") or line.startswith("import "):
                    continue
                # Skip docstrings at file level
                if line.strip().startswith('"""') and len(filtered_lines) == 0:
                    continue
                filtered_lines.append(line)

            combined_content.append(f"\n# --- {schema_file.stem.upper()} ---\n")
            combined_content.append("\n".join(filtered_lines))

    combined_output.write_text("".join(combined_content))
    print(f"Generated combined: {combined_output.relative_to(CONTRACTS_DIR)}")

    # Clean up temp directory
    import shutil
    shutil.rmtree(temp_dir)

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Pydantic models from JSON Schema definitions",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for generated models",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Generate a single combined model file",
    )

    args = parser.parse_args()
    output_dir = args.output_dir.resolve()

    print(f"Generating Pydantic models from: {SCHEMAS_DIR}")
    print(f"Output directory: {output_dir}")
    print()

    if args.combined:
        success = generate_combined_model(output_dir)
    else:
        success = generate_all_models(output_dir)

    if success:
        print("\nGeneration completed successfully!")
        return 0
    else:
        print("\nGeneration completed with errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
