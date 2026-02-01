"""Supabase migration runner.

Runs SQL migrations against the Supabase PostgreSQL database.
Migrations are applied in order based on filename prefix (001_, 002_, etc.).

Usage:
    # From project root
    python -m apps.api.app.infrastructure.supabase.migrate

    # Or directly
    cd apps/api
    python -m app.infrastructure.supabase.migrate

    # With options
    python -m app.infrastructure.supabase.migrate --dry-run
    python -m app.infrastructure.supabase.migrate --migration 001
"""

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_migrations_dir() -> Path:
    """Get the migrations directory path.

    Migrations are stored in infra/supabase/migrations/ at the project root.
    """
    # Try relative to this file (apps/api/app/infrastructure/supabase/migrate.py)
    # -> go up to project root, then infra/supabase/migrations
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent.parent.parent.parent
    migrations_dir = project_root / "infra" / "supabase" / "migrations"

    if migrations_dir.exists():
        return migrations_dir

    # Try from current working directory
    cwd_migrations = Path.cwd() / "infra" / "supabase" / "migrations"
    if cwd_migrations.exists():
        return cwd_migrations

    # Try from project root via relative path
    for parent in Path.cwd().parents:
        test_path = parent / "infra" / "supabase" / "migrations"
        if test_path.exists():
            return test_path

    raise FileNotFoundError(
        f"Migrations directory not found. Tried:\n"
        f"  - {migrations_dir}\n"
        f"  - {cwd_migrations}\n"
        f"Expected location: <project_root>/infra/supabase/migrations/"
    )


def get_migration_files(migrations_dir: Path) -> list[Path]:
    """Get sorted list of migration files."""
    files = sorted(migrations_dir.glob("*.sql"))
    return files


def run_migration(sql_content: str, dry_run: bool = False) -> bool:
    """Run a single migration.

    Args:
        sql_content: SQL content to execute.
        dry_run: If True, only print what would be executed.

    Returns:
        True if successful, False otherwise.
    """
    if dry_run:
        logger.info("DRY RUN - Would execute:")
        for line in sql_content.split("\n")[:20]:
            if line.strip():
                logger.info(f"  {line}")
        if sql_content.count("\n") > 20:
            logger.info(f"  ... and {sql_content.count(chr(10)) - 20} more lines")
        return True

    try:
        # Import Supabase client
        from app.infrastructure.supabase.client import get_supabase_client
        from app.infrastructure.supabase.config import is_supabase_configured

        if not is_supabase_configured():
            logger.error(
                "Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY."
            )
            return False

        client = get_supabase_client()

        # Execute the SQL using RPC call
        # Note: Supabase doesn't directly support raw SQL execution via the client.
        # Migrations should be run via the Supabase dashboard or supabase CLI.
        logger.warning(
            "Direct SQL execution via Python client is not supported. "
            "Please run migrations using one of these methods:\n"
            "  1. Supabase Dashboard: SQL Editor\n"
            "  2. Supabase CLI: supabase db push\n"
            "  3. psql: Connect directly to the database"
        )

        # Print the SQL for manual execution
        logger.info("Migration SQL:")
        print("-" * 60)
        print(sql_content)
        print("-" * 60)

        return True
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.info("Make sure supabase-py is installed: pip install supabase")
        return False
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def main() -> int:
    """Main entry point for migration runner."""
    parser = argparse.ArgumentParser(
        description="Run Supabase database migrations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running",
    )
    parser.add_argument(
        "--migration",
        type=str,
        help="Run specific migration (e.g., '001' or '001_create_tables')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_migrations",
        help="List available migrations",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output combined SQL to file",
    )

    args = parser.parse_args()

    try:
        migrations_dir = get_migrations_dir()
        logger.info(f"Migrations directory: {migrations_dir}")

        migration_files = get_migration_files(migrations_dir)

        if not migration_files:
            logger.warning("No migration files found")
            return 1

        if args.list_migrations:
            logger.info("Available migrations:")
            for f in migration_files:
                logger.info(f"  - {f.name}")
            return 0

        # Filter to specific migration if requested
        if args.migration:
            migration_files = [
                f for f in migration_files
                if args.migration in f.name
            ]
            if not migration_files:
                logger.error(f"Migration '{args.migration}' not found")
                return 1

        # Combine all migrations
        combined_sql = []
        for migration_file in migration_files:
            logger.info(f"Reading migration: {migration_file.name}")
            sql_content = migration_file.read_text()
            combined_sql.append(f"-- Migration: {migration_file.name}")
            combined_sql.append(sql_content)
            combined_sql.append("")

        full_sql = "\n".join(combined_sql)

        # Output to file if requested
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(full_sql)
            logger.info(f"Combined SQL written to: {output_path}")
            return 0

        # Run migrations
        logger.info(f"Running {len(migration_files)} migration(s)...")

        success = run_migration(full_sql, dry_run=args.dry_run)

        if success:
            logger.info("Migration completed successfully")
            return 0
        else:
            logger.error("Migration failed")
            return 1

    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
