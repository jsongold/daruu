"""Admin service for table browsing and record comparison."""

import logging

from app.infrastructure.supabase.client import get_supabase_client

logger = logging.getLogger(__name__)

ALLOWED_TABLES: dict[str, dict] = {
    "conversations": {"display_name": "Conversations", "exclude_columns": []},
    "prompt_logs": {"display_name": "Prompt Logs", "exclude_columns": []},
    "prompt_raw": {"display_name": "Prompt Raw", "exclude_columns": []},
    "form_schema": {"display_name": "Form Schema", "exclude_columns": ["embedding"]},
    "form_rules": {"display_name": "Form Rules", "exclude_columns": []},
    "annotation_pairs": {"display_name": "Annotation Pairs", "exclude_columns": []},
    "field_label_maps": {"display_name": "Field Label Maps", "exclude_columns": []},
    "messages": {"display_name": "Messages", "exclude_columns": []},
    "forms": {"display_name": "Forms", "exclude_columns": []},
}


def _validate_table(table: str) -> dict:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' is not allowed")
    return ALLOWED_TABLES[table]


def _strip_excluded(record: dict, exclude_columns: list[str]) -> dict:
    if not exclude_columns:
        return record
    return {k: v for k, v in record.items() if k not in exclude_columns}


class AdminService:
    def list_tables(self) -> list[dict]:
        return [
            {"name": name, "display_name": cfg["display_name"]}
            for name, cfg in ALLOWED_TABLES.items()
        ]

    def list_records(
        self,
        table: str,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        config = _validate_table(table)
        exclude = config["exclude_columns"]

        sb = get_supabase_client()
        result = (
            sb.table(table)
            .select("*")
            .order(sort_by, desc=(sort_order == "desc"))
            .limit(limit)
            .offset(offset)
            .execute()
        )
        data = result.data or []

        # Strip excluded columns
        data = [_strip_excluded(r, exclude) for r in data]

        # Client-side search filter
        if search:
            search_lower = search.lower()
            data = [
                r
                for r in data
                if any(search_lower in str(v).lower() for v in r.values())
            ]

        columns = list(data[0].keys()) if data else []
        return {"records": data, "columns": columns, "total": len(data)}

    def get_record(self, table: str, record_id: str) -> dict | None:
        config = _validate_table(table)
        exclude = config["exclude_columns"]

        sb = get_supabase_client()
        result = (
            sb.table(table)
            .select("*")
            .eq("id", record_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None

        return _strip_excluded(rows[0], exclude)
