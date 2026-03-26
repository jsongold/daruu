#!/usr/bin/env python3
"""Check contract consistency and drift detection.

This script verifies that:
1. OpenAPI spec matches the FastAPI implementation
2. JSON schemas are valid
3. Examples validate against schemas
4. TypeScript types are up to date

Usage:
    python scripts/check_contracts.py
    python scripts/check_contracts.py --fix  # Regenerate all contracts
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Paths
CONTRACTS_DIR = Path(__file__).parent.parent
API_DIR = CONTRACTS_DIR.parent / "api"
WEB_DIR = CONTRACTS_DIR.parent / "web"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
OPENAPI_DIR = CONTRACTS_DIR / "openapi"


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = True,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def check_json_schemas() -> list[str]:
    """Validate all JSON schemas are valid draft-07."""
    issues: list[str] = []

    try:
        from jsonschema import Draft7Validator
    except ImportError:
        issues.append("jsonschema not installed")
        return issues

    for schema_file in SCHEMAS_DIR.glob("*.json"):
        try:
            with open(schema_file, encoding="utf-8") as f:
                schema = json.load(f)

            # Check it has required fields
            if "$schema" not in schema:
                issues.append(f"{schema_file.name}: missing $schema")

            if "$id" not in schema:
                issues.append(f"{schema_file.name}: missing $id")

            # Validate schema is valid
            Draft7Validator.check_schema(schema)

        except json.JSONDecodeError as e:
            issues.append(f"{schema_file.name}: invalid JSON - {e}")
        except Exception as e:
            issues.append(f"{schema_file.name}: {e}")

    return issues


def check_openapi_spec() -> list[str]:
    """Validate OpenAPI specification."""
    issues: list[str] = []

    try:
        import yaml
        from openapi_spec_validator import validate
        from openapi_spec_validator.readers import read_from_filename
    except ImportError:
        issues.append("openapi-spec-validator not installed")
        return issues

    for spec_file in OPENAPI_DIR.glob("*.yaml"):
        try:
            spec_dict, _ = read_from_filename(str(spec_file))
            validate(spec_dict)
        except Exception as e:
            issues.append(f"{spec_file.name}: {e}")

    return issues


def check_openapi_sync() -> tuple[bool, str]:
    """Check if OpenAPI JSON matches FastAPI implementation.

    Returns:
        Tuple of (in_sync, message)
    """
    openapi_json = OPENAPI_DIR / "openapi.json"

    if not openapi_json.exists():
        return False, "openapi.json does not exist"

    # Run export script with --check flag
    script_path = CONTRACTS_DIR / "scripts" / "export_openapi.py"

    code, stdout, stderr = run_command(
        [sys.executable, str(script_path), "--check", "--output", str(openapi_json)],
        cwd=API_DIR,
    )

    if code == 0:
        return True, "OpenAPI spec is in sync"
    else:
        return False, stderr or "OpenAPI spec differs from implementation"


def check_typescript_sync() -> tuple[bool, str]:
    """Check if TypeScript types are up to date.

    Returns:
        Tuple of (in_sync, message)
    """
    ts_file = WEB_DIR / "src" / "lib" / "api-types.ts"

    if not ts_file.exists():
        return False, "api-types.ts does not exist"

    # Check file age vs openapi.yaml
    openapi_yaml = OPENAPI_DIR / "api.yaml"
    if openapi_yaml.exists():
        yaml_mtime = openapi_yaml.stat().st_mtime
        ts_mtime = ts_file.stat().st_mtime

        if yaml_mtime > ts_mtime:
            return False, "TypeScript types are older than OpenAPI spec"

    return True, "TypeScript types appear up to date"


def run_contract_tests() -> tuple[int, str]:
    """Run contract test suite.

    Returns:
        Tuple of (exit_code, output)
    """
    code, stdout, stderr = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=CONTRACTS_DIR,
    )

    output = stdout + stderr
    return code, output


def regenerate_openapi() -> bool:
    """Regenerate OpenAPI JSON from FastAPI."""
    script_path = CONTRACTS_DIR / "scripts" / "export_openapi.py"
    output_path = OPENAPI_DIR / "openapi.json"

    code, _, stderr = run_command(
        [sys.executable, str(script_path), "--output", str(output_path)],
        cwd=API_DIR,
    )

    return code == 0


def regenerate_typescript() -> bool:
    """Regenerate TypeScript types from OpenAPI."""
    script_path = CONTRACTS_DIR / "scripts" / "generate_typescript.py"

    code, _, stderr = run_command(
        [sys.executable, str(script_path)],
        cwd=CONTRACTS_DIR,
    )

    return code == 0


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check contract consistency and drift")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Regenerate contracts to fix drift",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running contract tests",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()

    all_passed = True
    issues: list[str] = []

    print("Checking contracts...")
    print()

    # 1. Check JSON schemas
    print("1. Validating JSON schemas...")
    schema_issues = check_json_schemas()
    if schema_issues:
        all_passed = False
        issues.extend(schema_issues)
        print(f"   FAILED: {len(schema_issues)} issues found")
        if args.verbose:
            for issue in schema_issues:
                print(f"      - {issue}")
    else:
        print("   OK")

    # 2. Check OpenAPI specs
    print("2. Validating OpenAPI specs...")
    openapi_issues = check_openapi_spec()
    if openapi_issues:
        all_passed = False
        issues.extend(openapi_issues)
        print(f"   FAILED: {len(openapi_issues)} issues found")
        if args.verbose:
            for issue in openapi_issues:
                print(f"      - {issue}")
    else:
        print("   OK")

    # 3. Check OpenAPI sync
    print("3. Checking OpenAPI sync with FastAPI...")
    in_sync, msg = check_openapi_sync()
    if not in_sync:
        if args.fix:
            print("   Regenerating OpenAPI...")
            if regenerate_openapi():
                print("   FIXED: OpenAPI regenerated")
            else:
                all_passed = False
                issues.append("Failed to regenerate OpenAPI")
                print("   FAILED: Could not regenerate")
        else:
            all_passed = False
            issues.append(msg)
            print(f"   FAILED: {msg}")
    else:
        print("   OK")

    # 4. Check TypeScript sync
    print("4. Checking TypeScript types...")
    in_sync, msg = check_typescript_sync()
    if not in_sync:
        if args.fix:
            print("   Regenerating TypeScript types...")
            if regenerate_typescript():
                print("   FIXED: TypeScript types regenerated")
            else:
                all_passed = False
                issues.append("Failed to regenerate TypeScript")
                print("   FAILED: Could not regenerate")
        else:
            all_passed = False
            issues.append(msg)
            print(f"   FAILED: {msg}")
    else:
        print("   OK")

    # 5. Run contract tests
    if not args.skip_tests:
        print("5. Running contract tests...")
        test_code, test_output = run_contract_tests()
        if test_code != 0:
            all_passed = False
            issues.append("Contract tests failed")
            print("   FAILED")
            if args.verbose:
                print(test_output)
        else:
            print("   OK")
    else:
        print("5. Contract tests skipped")

    print()
    if all_passed:
        print("All contract checks passed!")
        sys.exit(0)
    else:
        print(f"Contract checks failed with {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("Run with --fix to regenerate contracts.")
        sys.exit(1)


if __name__ == "__main__":
    main()
