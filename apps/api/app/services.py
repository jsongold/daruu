"""Business logic services: FormService, AnnotationService, ConversationService, MappingService, MapService, FillService."""

import base64
import difflib
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from uuid import uuid4

import fitz  # PyMuPDF
from app.config import get_settings
from app.infrastructure.supabase.client import get_supabase_client
from app.context import ContextService
from app.prompts import AskPrompt, FillPrompt, MapPrompt, RulesPrompt
from app.models import (
    AskContext,
    Annotation,
    AnnotationEntry,
    AnnotationOperation,
    BBox,
    Message,
    ContextWindow,
    CreateAnnotationRequest,
    FieldLabelMap,
    FieldType,
    Form,
    FormField,
    FormRules,
    FormSchema,
    FormSchemaField,
    HistoryMessage,
    MapContext,
    MapResult,
    MapRun,
    Mapping,
    Mode,
    PromptLog,
    RuleItem,
    RulesContext,
    RuleType,
    Rules,
    TextBlock,
    UserInfo,
)

logger = logging.getLogger(__name__)


@contextmanager
def _log_step(step: str, **ctx: object) -> Generator[None, None, None]:
    """Context manager that logs start/success/error for a named step."""
    label = " ".join(f"{k}={v}" for k, v in ctx.items())
    logger.info("%s started: %s", step, label)
    try:
        yield
        logger.info("%s succeeded: %s", step, label)
    except Exception as e:
        logger.error("%s failed: %s | %s", step, label, e)
        raise


def _save_prompt_log(
    *,
    type: str,
    prompt_template: str,
    model: str,
    system_chars: int,
    user_chars: int,
    started_at: datetime,
    conversation_id: str | None = None,
    message_id: str | None = None,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> str | None:
    """Persist a prompt log entry to Supabase before the LLM call. Returns row id or None on failure."""
    try:
        supabase = get_supabase_client()
        response = supabase.table("prompt_logs").insert({
            "conversation_id": conversation_id,
            "message_id": message_id,
            "type": type,
            "prompt_template": prompt_template,
            "model": model,
            "system_chars": system_chars,
            "user_chars": user_chars,
            "started_at": started_at.isoformat(),
        }).execute()

        prompt_log_id: str = response.data[0]["id"]

        if system_prompt is not None or user_prompt is not None:
            supabase.table("prompt_raw").insert({
                "prompt_log_id": prompt_log_id,
                "system_prompt": system_prompt or "",
                "user_prompt": user_prompt or "",
            }).execute()

        return prompt_log_id
    except Exception as e:
        logger.warning("Failed to save prompt log: %s", e)
        return None


def _end_prompt_log(prompt_log_id: str | None, ended_at: datetime) -> None:
    """Update ended_at on a prompt_log row after a successful LLM call. Non-fatal."""
    if prompt_log_id is None:
        return
    try:
        get_supabase_client().table("prompt_logs").update(
            {"ended_at": ended_at.isoformat()}
        ).eq("id", prompt_log_id).execute()
    except Exception as e:
        logger.warning("Failed to update prompt_log ended_at: %s", e)


_FIELD_TYPE_MAP: dict[str, FieldType] = {
    "text": FieldType.TEXT,
    "checkbox": FieldType.CHECKBOX,
    "radiobutton": FieldType.RADIO,
    "combobox": FieldType.SELECT,
    "listbox": FieldType.SELECT,
    "signature": FieldType.SIGNATURE,
}


def _to_field_type(type_string: str) -> FieldType:
    return _FIELD_TYPE_MAP.get(type_string.lower(), FieldType.UNKNOWN)


def _bbox_to_dict(bbox: BBox | None) -> dict | None:
    if bbox is None:
        return None
    return {"x": bbox.x, "y": bbox.y, "width": bbox.width, "height": bbox.height}


def _dict_to_bbox(d: dict | None) -> BBox | None:
    if d is None:
        return None
    return BBox(x=d["x"], y=d["y"], width=d["width"], height=d["height"])


class FormService:
    """Handles PDF form upload, preview, and field extraction."""

    def upload_pdf(self, file_bytes: bytes, filename: str) -> Form:
        settings = get_settings()
        form_id = str(uuid4())
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{form_id}.pdf"
        file_path.write_bytes(file_bytes)

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        fields = self._extract_fields(doc, form_id)
        doc.close()

        supabase = get_supabase_client()
        supabase.table("forms").insert(
            {
                "id": form_id,
                "ref": str(file_path),
                "form_type": "target",
                "meta": {
                    "filename": filename,
                    "page_count": page_count,
                    "file_size": len(file_bytes),
                    "mime_type": "application/pdf",
                },
            }
        ).execute()

        form = Form(
            id=str(uuid4()),
            form_id=form_id,
            fields=fields,
            page_count=page_count,
        )

        # Seed form_schema with baseline field data from PDF extraction
        try:
            FormSchemaService().ensure_schema(form_id)
        except Exception as e:
            logger.warning("Failed to seed form_schema for %s: %s", form_id, e)

        return form

    def _extract_fields(self, doc: fitz.Document, form_id: str) -> list[FormField]:
        fields: list[FormField] = []
        for page_num, page in enumerate(doc, start=1):
            page_w = page.rect.width or 1.0
            page_h = page.rect.height or 1.0
            for widget in page.widgets():
                bbox = BBox(
                    x=widget.rect.x0 / page_w,
                    y=widget.rect.y0 / page_h,
                    width=(widget.rect.x1 - widget.rect.x0) / page_w,
                    height=(widget.rect.y1 - widget.rect.y0) / page_h,
                )
                field_name = widget.field_name or f"field_{len(fields)}"
                stable_id = str(len(fields))
                raw_choices = getattr(widget, "choice_values", None) or []
                options = [str(c) for c in raw_choices] if raw_choices else []
                fields.append(
                    FormField(
                        id=stable_id,
                        name=field_name,
                        field_type=_to_field_type(widget.field_type_string or ""),
                        bbox=bbox,
                        page=page_num,
                        value=widget.field_value if isinstance(widget.field_value, str) else None,
                        options=options,
                    )
                )
        return fields

    def _get_file_path(self, form_id: str) -> Path:
        settings = get_settings()
        return Path(settings.upload_dir) / f"{form_id}.pdf"

    def get_page_count(self, form_id: str) -> int:
        file_path = self._get_file_path(form_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Form file not found: {form_id}")
        doc = fitz.open(str(file_path))
        count = len(doc)
        doc.close()
        return count

    def get_page_preview_base64(self, form_id: str, page: int) -> str:
        file_path = self._get_file_path(form_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Form file not found: {form_id}")

        doc = fitz.open(str(file_path))
        if page < 1 or page > len(doc):
            doc.close()
            raise ValueError(f"Page {page} out of range for form {form_id}")

        pdf_page = doc[page - 1]
        mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
        pix = pdf_page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        doc.close()

        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def get_fields_and_text_blocks(
        self, form_id: str
    ) -> tuple[list[FormField], list[TextBlock]]:
        file_path = self._get_file_path(form_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Form file not found: {form_id}")

        doc = fitz.open(str(file_path))
        fields = self._extract_fields(doc, form_id)
        text_blocks: list[TextBlock] = []

        for page_num, page in enumerate(doc, start=1):
            page_w = page.rect.width or 1.0
            page_h = page.rect.height or 1.0
            words = page.get_text("words")  # (x0,y0,x1,y1,word,block_no,line_no,word_no)

            # Group words into lines by proximity (same block_no + line_no)
            line_groups: dict[tuple[int, int], list] = {}
            for w in words:
                key = (int(w[5]), int(w[6]))  # block_no, line_no
                line_groups.setdefault(key, []).append(w)

            for (block_no, line_no), line_words in line_groups.items():
                line_words_sorted = sorted(line_words, key=lambda w: w[0])
                text = " ".join(w[4] for w in line_words_sorted)
                x0 = min(w[0] for w in line_words_sorted)
                y0 = min(w[1] for w in line_words_sorted)
                x1 = max(w[2] for w in line_words_sorted)
                y1 = max(w[3] for w in line_words_sorted)
                bbox = BBox(
                    x=x0 / page_w,
                    y=y0 / page_h,
                    width=(x1 - x0) / page_w,
                    height=(y1 - y0) / page_h,
                )
                text_blocks.append(
                    TextBlock(
                        id=str(uuid4()),
                        text=text,
                        bbox=bbox,
                        page=page_num,
                    )
                )

        doc.close()
        return fields, text_blocks


class AnnotationService:
    """Append-only changelog for spatial label-field annotation pairs.

    Uses the form_annotation_pairs table.
    The public interface still returns Annotation projection objects so
    FormSchemaService and MapService need no changes.
    """

    TABLE = "form_annotation_pairs"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _current_pairs(self, form_id: str) -> list[Annotation]:
        """Replay annotation changelog rows to compute currently active pairs."""
        supabase = get_supabase_client()
        result = (
            supabase.table(self.TABLE)
            .select("*")
            .eq("form_id", form_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []

        # Group by pair_id
        from collections import defaultdict
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[row["pair_id"]].append(row)

        annotations: list[Annotation] = []
        for pair_id, entries in groups.items():
            label_added = [e for e in entries if e["role"] == "label" and e["operation"] == "added"]
            label_removed = [e for e in entries if e["role"] == "label" and e["operation"] == "removed"]
            field_added = [e for e in entries if e["role"] == "field" and e["operation"] == "added"]
            field_removed = [e for e in entries if e["role"] == "field" and e["operation"] == "removed"]

            label_net = len(label_added) - len(label_removed)
            field_net = len(field_added) - len(field_removed)

            if label_net <= 0 or field_net <= 0:
                continue

            latest_label = label_added[-1]
            latest_field = field_added[-1]

            try:
                annotations.append(
                    Annotation(
                        id=pair_id,
                        form_id=form_id,
                        label_text=latest_label["value"],
                        label_bbox=BBox(**latest_label["bbox"]),
                        label_page=latest_label.get("page", 1),
                        field_id=latest_field["field_id"],
                        field_name=latest_field["value"],
                        field_bbox=_dict_to_bbox(latest_field.get("bbox")),
                        field_page=latest_field.get("page", 1),
                        created_at=datetime.fromisoformat(latest_label["created_at"])
                        if latest_label.get("created_at")
                        else None,
                    )
                )
            except Exception as e:
                logger.warning("Failed to reconstruct annotation pair %s: %s", pair_id, e)

        return annotations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, req: CreateAnnotationRequest) -> Annotation:
        pair_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        supabase = get_supabase_client()

        # Auto-remove any existing active annotation for the same field_id
        existing = [a for a in self._current_pairs(req.form_id) if a.field_id == req.field_id]
        if existing:
            old = existing[-1]
            supabase.table(self.TABLE).insert([
                {
                    "form_id": req.form_id,
                    "pair_id": old.id,
                        "operation": AnnotationOperation.REMOVED.value,
                    "role": "label",
                    "value": old.label_text,
                    "bbox": _bbox_to_dict(old.label_bbox),
                    "page": old.label_page,
                    "field_id": None,
                        "created_at": now,
                },
                {
                    "form_id": req.form_id,
                    "pair_id": old.id,
                        "operation": AnnotationOperation.REMOVED.value,
                    "role": "field",
                    "value": old.field_name,
                    "bbox": _bbox_to_dict(old.field_bbox),
                    "page": old.field_page,
                    "field_id": old.field_id,
                        "created_at": now,
                },
            ]).execute()

        supabase.table(self.TABLE).insert([
            {
                "form_id": req.form_id,
                "pair_id": pair_id,
                "operation": AnnotationOperation.ADDED.value,
                "role": "label",
                "value": req.label_text,
                "bbox": _bbox_to_dict(req.label_bbox),
                "page": req.label_page,
                "field_id": None,
                "created_at": now,
            },
            {
                "form_id": req.form_id,
                "pair_id": pair_id,
                "operation": AnnotationOperation.ADDED.value,
                "role": "field",
                "value": req.field_name,
                "bbox": _bbox_to_dict(req.field_bbox),
                "page": req.field_page,
                "field_id": req.field_id,
                "created_at": now,
            },
        ]).execute()

        annotation = Annotation(
            id=pair_id,
            form_id=req.form_id,
            label_text=req.label_text,
            label_bbox=req.label_bbox,
            label_page=req.label_page,
            field_id=req.field_id,
            field_name=req.field_name,
            field_bbox=req.field_bbox,
            field_page=req.field_page,
            created_at=datetime.fromisoformat(now),
        )

        try:
            FormSchemaService().upsert_from_annotation(req.form_id, annotation)
        except Exception as e:
            logger.warning("Failed to update form_schema from annotation: %s", e)

        return annotation

    def list_by_form(self, form_id: str) -> list[Annotation]:
        return self._current_pairs(form_id)

    def delete(self, annotation_id: str) -> None:
        """annotation_id is the pair_id. Appends removed rows (never deletes)."""
        supabase = get_supabase_client()

        # Fetch the latest added rows for this pair to get current values
        result = (
            supabase.table(self.TABLE)
            .select("*")
            .eq("pair_id", annotation_id)
            .eq("operation", "added")
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []

        label_row = next((r for r in rows if r["role"] == "label"), None)
        field_row = next((r for r in rows if r["role"] == "field"), None)

        if not label_row or not field_row:
            logger.warning("Annotation pair %s not found for deletion", annotation_id)
            return

        now = datetime.now(timezone.utc).isoformat()
        supabase.table(self.TABLE).insert([
            {
                "form_id": label_row["form_id"],
                "pair_id": annotation_id,
                "operation": AnnotationOperation.REMOVED.value,
                "role": "label",
                "value": label_row["value"],
                "bbox": label_row.get("bbox"),
                "page": label_row.get("page", 1),
                "field_id": None,
                "created_at": now,
            },
            {
                "form_id": field_row["form_id"],
                "pair_id": annotation_id,
                "operation": AnnotationOperation.REMOVED.value,
                "role": "field",
                "value": field_row["value"],
                "bbox": field_row.get("bbox"),
                "page": field_row.get("page", 1),
                "field_id": field_row.get("field_id"),
                "created_at": now,
            },
        ]).execute()

        try:
            FormSchemaService().remove_annotation(label_row["form_id"], field_row["field_id"])
        except Exception as e:
            logger.warning("Failed to revert form_schema after annotation delete: %s", e)


class ConversationService:
    """Manages ContextWindow conversations in Supabase."""

    def create(self, form_id: str | None, user_info: UserInfo, rules: Rules) -> ContextWindow:
        conversation_id = str(uuid4())
        now = datetime.now(timezone.utc)

        supabase = get_supabase_client()
        supabase.table("conversations").insert(
            {
                "id": conversation_id,
                "form_id": form_id,
                "user_info": user_info.model_dump(),
                "mode": Mode.PREVIEW.value,
                "history": [],
                "rules": rules.model_dump(),
                "ask_answers": {},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        ).execute()

        return ContextWindow(
            conversation_id=conversation_id,
            form_id=form_id,
            user_info=user_info,
            rules=rules,
            mode=Mode.PREVIEW,
            created_at=now,
            updated_at=now,
        )

    def get(self, conversation_id: str) -> ContextWindow | None:
        supabase = get_supabase_client()
        result = (
            supabase.table("conversations").select("*").eq("id", conversation_id).execute()
        )
        rows = result.data if hasattr(result, "data") else []
        if not rows:
            return None
        row = rows[0]

        try:
            user_info = UserInfo(**row.get("user_info", {}))
            rules = Rules(**row.get("rules", {"items": []}))
            history = [HistoryMessage(**m) for m in row.get("history", [])]
            form_values: dict[str, str] = row.get("form_values") or {}
            ask_answers: dict[str, str] = row.get("ask_answers") or {}

            return ContextWindow(
                conversation_id=row["id"],
                form_id=row.get("form_id"),
                user_info=user_info,
                rules=rules,
                rulebook_url=row.get("rulebook_url"),
                mode=Mode(row.get("mode", Mode.PREVIEW.value)),
                history=history,
                form_values=form_values,
                ask_answers=ask_answers,
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            )
        except Exception as e:
            logger.error("Failed to parse conversation %s: %s", conversation_id, e)
            return None

    def update_form(self, conversation_id: str, form_id: str) -> None:
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {"form_id": form_id, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

    def update_mode(self, conversation_id: str, mode: Mode) -> None:
        logger.info("Mode transition: conversation=%s mode=%s", conversation_id, mode.value)
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {"mode": mode.value, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

    def add_history(self, conversation_id: str, role: str, content: str) -> None:
        self.add_history_batch(conversation_id, [(role, content)])

    def add_history_batch(self, conversation_id: str, messages: list[tuple[str, str]]) -> None:
        ctx = self.get(conversation_id)
        if ctx is None:
            logger.warning("Conversation %s not found for add_history_batch", conversation_id)
            return
        updated = list(ctx.history) + [HistoryMessage(role=r, content=c) for r, c in messages]
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {
                "history": [m.model_dump() for m in updated],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", conversation_id).execute()

    def update_user_info(self, conversation_id: str, data: dict) -> None:
        """Merge new key/value pairs into conversation user_info.data."""
        ctx = self.get(conversation_id)
        if ctx is None:
            return
        merged = {**ctx.user_info.data, **data}
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {"user_info": {"data": merged}, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

    def update_ask_answers(self, conversation_id: str, new_answers: dict[str, str]) -> None:
        """Merge new question->answer pairs into conversation ask_answers."""
        ctx = self.get(conversation_id)
        if ctx is None:
            return
        merged = {**ctx.ask_answers, **new_answers}
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {"ask_answers": merged, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

    def update_form_values(self, conversation_id: str, new_values: dict[str, str]) -> None:
        """Merge new field_id->value pairs into conversation form_values."""
        ctx = self.get(conversation_id)
        if ctx is None:
            return
        merged = {**ctx.form_values, **new_values}
        supabase = get_supabase_client()
        supabase.table("conversations").update(
            {"form_values": merged, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

    def update_rules(self, conversation_id: str, rule_items: list["RuleItem"], rulebook_url: str | None = None) -> None:
        """Replace conversation rules with a new list of RuleItem objects."""
        supabase = get_supabase_client()
        payload: dict = {
            "rules": {"items": [i.model_dump() for i in rule_items]},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if rulebook_url is not None:
            payload["rulebook_url"] = rulebook_url
        payload["ask_answers"] = {}
        supabase.table("conversations").update(payload).eq("id", conversation_id).execute()


class UnderstandService:
    """Analyzes a form and extracts filling rules via LLM."""

    def __init__(self) -> None:
        self._conversation_service = ConversationService()
        self._form_service = FormService()

    def understand(self, conversation_id: str) -> None:
        """Run LLM analysis on the form and persist extracted rules to the conversation."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        ctx = self._conversation_service.get(conversation_id)
        if ctx is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        if not ctx.form_id:
            raise ValueError("Conversation has no associated form")

        fields, text_blocks = self._form_service.get_fields_and_text_blocks(ctx.form_id)
        rules_ctx = RulesContext(fields=fields, text_blocks=text_blocks)
        prompt = RulesPrompt.build(rules_ctx)

        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        started_at = datetime.now(timezone.utc)
        prompt_log_id = _save_prompt_log(
            type="understand",
            prompt_template="RulesPrompt",
            model=settings.openai_model,
            system_chars=len(prompt.system),
            user_chars=len(prompt.user),
            started_at=started_at,
            conversation_id=conversation_id,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
        )

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            response_format={"type": "json_object"},
        )

        _end_prompt_log(prompt_log_id, datetime.now(timezone.utc))

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)

        rulebook_text: str = result.get("rulebook_text", "")
        raw_rules = result.get("rules", [])
        rule_items = [
            RuleItem(
                type=RuleType(r.get("type", "format")),
                rule_text=str(r.get("rule_text", "")),
                field_ids=[str(fid) for fid in r.get("field_ids", [])],
                question=r.get("question") or None,
                options=[str(o) for o in r.get("options", [])],
            )
            for r in raw_rules
            if r.get("rule_text")
        ]

        rulebook_url: str | None = None
        if rulebook_text and ctx.form_id:
            try:
                supabase = get_supabase_client()
                key = f"{ctx.form_id}/rulebook.md"
                supabase.storage.from_("rulebooks").upload(
                    key,
                    rulebook_text.encode("utf-8"),
                    {"content-type": "text/markdown; charset=utf-8"},
                )
                rulebook_url = supabase.storage.from_("rulebooks").get_public_url(key)
            except Exception as e:
                logger.warning("Failed to upload rulebook to storage: %s", e)

        self._conversation_service.update_rules(conversation_id, rule_items, rulebook_url)

        # Persist rules globally to form_rules and link to form_schema
        if ctx.form_id:
            try:
                detected_description = result.get("description") or None
                form_rules_service = FormRulesService()
                form_rules = form_rules_service.upsert(
                    form_id=ctx.form_id,
                    rule_items=rule_items,
                    description=detected_description,
                    rulebook_text=rulebook_text or None,
                )
                FormSchemaService().link_rules(ctx.form_id, form_rules.id)
            except Exception as e:
                logger.warning("Failed to persist form_rules for %s: %s", ctx.form_id, e)


class MappingService:
    """Maps annotations to form fields using fuzzy matching + optional LLM fallback."""

    def map(
        self, conversation_id: str, form: Form, annotations: list[Annotation]
    ) -> list[Mapping]:
        mappings: list[Mapping] = []

        for annotation in annotations:
            best_field: FormField | None = None
            best_ratio = 0.0

            for field in form.fields:
                ratio = difflib.SequenceMatcher(
                    None, annotation.label_text.lower(), field.name.lower()
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_field = field

            if best_field and best_ratio > 0.6:
                mapping = self._save_mapping(
                    conversation_id=conversation_id,
                    annotation_id=annotation.id,
                    field_id=best_field.id,
                    confidence=best_ratio,
                    reason="fuzzy_match",
                )
                mappings.append(mapping)
            else:
                # Try LLM fallback if configured
                llm_mapping = self._llm_map(conversation_id, annotation, form)
                if llm_mapping:
                    mappings.append(llm_mapping)

        return mappings

    def _save_mapping(
        self,
        conversation_id: str,
        annotation_id: str,
        field_id: str,
        inferred_value: str | None = None,
        confidence: float = 0.0,
        reason: str = "",
    ) -> Mapping:
        mapping = Mapping(
            id=str(uuid4()),
            conversation_id=conversation_id,
            annotation_id=annotation_id,
            field_id=field_id,
            inferred_value=inferred_value,
            confidence=confidence,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        supabase = get_supabase_client()
        supabase.table("form_mappings").insert(
            {
                "id": mapping.id,
                "conversation_id": mapping.conversation_id,
                "annotation_id": mapping.annotation_id,
                "field_id": mapping.field_id,
                "inferred_value": mapping.inferred_value,
                "confidence": mapping.confidence,
                "reason": mapping.reason,
                "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
            }
        ).execute()
        return mapping

    def _llm_map(
        self, conversation_id: str, annotation: Annotation, form: Form
    ) -> Mapping | None:
        settings = get_settings()
        if not settings.openai_api_key:
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            field_names = [f.name for f in form.fields]
            prompt = (
                f"Match the label '{annotation.label_text}' to the best form field from this list:\n"
                f"{json.dumps(field_names)}\n\n"
                "Respond with JSON: {\"field_name\": \"<best match>\", \"confidence\": <0.0-1.0>, \"reason\": \"<reason>\"}"
            )
            started_at = datetime.now(timezone.utc)
            prompt_log_id = _save_prompt_log(
                type="mapping_fallback",
                prompt_template="inline",
                model=settings.openai_model,
                system_chars=0,
                user_chars=len(prompt),
                started_at=started_at,
                conversation_id=conversation_id,
                user_prompt=prompt,
            )

            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            _end_prompt_log(prompt_log_id, datetime.now(timezone.utc))
            result = json.loads(response.choices[0].message.content or "{}")
            matched_name = result.get("field_name")
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "llm_match")

            matched_field = next((f for f in form.fields if f.name == matched_name), None)
            if matched_field and confidence > 0.5:
                return self._save_mapping(
                    conversation_id=conversation_id,
                    annotation_id=annotation.id,
                    field_id=matched_field.id,
                    confidence=confidence,
                    reason=reason,
                )
        except Exception as e:
            logger.warning("LLM mapping failed for annotation %s: %s", annotation.id, e)

        return None

    def list_by_conversation(self, conversation_id: str) -> list[Mapping]:
        supabase = get_supabase_client()
        result = (
            supabase.table("form_mappings")
            .select("*")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        mappings: list[Mapping] = []
        for row in rows:
            try:
                mappings.append(
                    Mapping(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        annotation_id=row["annotation_id"],
                        field_id=row["field_id"],
                        inferred_value=row.get("inferred_value"),
                        confidence=float(row.get("confidence", 0.0)),
                        reason=row.get("reason", ""),
                        created_at=datetime.fromisoformat(row["created_at"])
                        if row.get("created_at")
                        else None,
                    )
                )
            except Exception as e:
                logger.warning("Failed to parse mapping row %s: %s", row.get("id"), e)
        return mappings


class MapService:
    """Identifies which text label belongs to each form field using spatial analysis + LLM."""

    def run(self, form_id: str, conversation_id: str | None = None) -> list[FieldLabelMap]:
        """Run spatial candidate filtering + LLM to identify field labels, persist results."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        form_service = FormService()
        fields, text_blocks = form_service.get_fields_and_text_blocks(form_id)
        annotations = AnnotationService().list_by_form(form_id)

        existing_heuristic = self._get_heuristic_maps(form_id)
        map_ctx = MapContext(
            fields=fields, text_blocks=text_blocks,
            confirmed_annotations=annotations,
            heuristic_maps=existing_heuristic,
        )
        prompt = MapPrompt.build(map_ctx)
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        started_at = datetime.now(timezone.utc)
        prompt_log_id = _save_prompt_log(
            type="map",
            prompt_template="MapPrompt",
            model=settings.openai_model,
            system_chars=len(prompt.system),
            user_chars=len(prompt.user),
            started_at=started_at,
            conversation_id=conversation_id,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
        )

        with _log_step("map.llm", form=form_id, fields=len(fields), prompt_chars=len(prompt.user)):
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                response_format={"type": "json_object"},
            )

        _end_prompt_log(prompt_log_id, datetime.now(timezone.utc))

        raw = response.choices[0].message.content or "{}"
        with _log_step("map.parse", form=form_id):
            parsed = json.loads(raw)
            items = parsed.get("results", [])
            detected_form_name = parsed.get("form_name") or None
            logger.info("map.parse items=%d form_name=%s raw_chars=%d", len(items), detected_form_name, len(raw))

        field_map = {f.id: f for f in fields}
        now = datetime.now(timezone.utc)
        results: list[FieldLabelMap] = []
        for item in items:
            field_id = item.get("field_id")
            if not field_id or field_id not in field_map:
                continue
            results.append(FieldLabelMap(
                id=str(uuid4()),
                form_id=form_id,
                field_id=field_id,
                field_name=field_map[field_id].name,
                label_text=item.get("label"),
                semantic_key=item.get("semantic_key"),
                confidence=int(item.get("confidence", 0)),
                source="auto",
                created_at=now,
            ))

        if not results:
            logger.warning("map.save skipped: form=%s items=%d fields=%d (no matches)", form_id, len(items), len(fields))
            return results

        supabase = get_supabase_client()
        with _log_step("map.save", form=form_id, rows=len(results)):
            supabase.table("field_label_maps").insert([
                {
                    "id": r.id,
                    "form_id": r.form_id,
                    "field_id": r.field_id,
                    "field_name": r.field_name,
                    "label_text": r.label_text,
                    "semantic_key": r.semantic_key,
                    "confidence": r.confidence,
                    "source": r.source,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in results
            ]).execute()

        # Update global form_schema with map results + form_name
        try:
            FormSchemaService().upsert_from_map(form_id, results, form_name=detected_form_name)
        except Exception as e:
            logger.warning("Failed to update form_schema from map: %s", e)

        return results

    def run_heuristic(self, form_id: str) -> list[FieldLabelMap]:
        """Assign labels to fields using spatial heuristics only (no LLM)."""
        from app.spatial import direction_score, is_decoration, score_to_confidence

        form_service = FormService()
        fields, text_blocks = form_service.get_fields_and_text_blocks(form_id)

        valid_blocks = [b for b in text_blocks if not is_decoration(b.text)]

        fields_by_page: dict[int, list] = {}
        for f in fields:
            fields_by_page.setdefault(f.page, []).append(f)
        blocks_by_page: dict[int, list] = {}
        for b in valid_blocks:
            blocks_by_page.setdefault(b.page, []).append(b)

        scored_pairs: list[tuple[float, str, object, object]] = []
        for page, page_fields in fields_by_page.items():
            page_blocks = blocks_by_page.get(page, [])
            for field in page_fields:
                if field.bbox is None:
                    continue
                fb = (field.bbox.x, field.bbox.y, field.bbox.width, field.bbox.height)
                for block in page_blocks:
                    bb = (block.bbox.x, block.bbox.y, block.bbox.width, block.bbox.height)
                    score, direction = direction_score(fb, bb)
                    scored_pairs.append((score, direction, field, block))

        scored_pairs.sort(key=lambda t: t[0])

        assigned_fields: set[str] = set()
        assigned_labels: set[str] = set()
        results: list[FieldLabelMap] = []
        now = datetime.now(timezone.utc)

        for score, _dir, field, block in scored_pairs:
            if field.id in assigned_fields or block.id in assigned_labels:
                continue
            confidence = score_to_confidence(score)
            if confidence < 5:
                continue
            assigned_fields.add(field.id)
            assigned_labels.add(block.id)
            results.append(FieldLabelMap(
                id=str(uuid4()),
                form_id=form_id,
                field_id=field.id,
                field_name=field.name,
                label_text=block.text,
                semantic_key=None,
                confidence=confidence,
                source="heuristic",
                created_at=now,
            ))

        if not results:
            logger.warning("heuristic_map.save skipped: form=%s fields=%d blocks=%d (no matches)",
                           form_id, len(fields), len(valid_blocks))
            return results

        supabase = get_supabase_client()
        with _log_step("heuristic_map.save", form=form_id, rows=len(results)):
            supabase.table("field_label_maps").insert([
                {
                    "id": r.id,
                    "form_id": r.form_id,
                    "field_id": r.field_id,
                    "field_name": r.field_name,
                    "label_text": r.label_text,
                    "semantic_key": r.semantic_key,
                    "confidence": r.confidence,
                    "source": r.source,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in results
            ]).execute()

        try:
            FormSchemaService().upsert_from_map(form_id, results, form_name=None)
        except Exception as e:
            logger.warning("Failed to update form_schema from heuristic map: %s", e)

        return results

    def _get_heuristic_maps(self, form_id: str) -> list[FieldLabelMap]:
        """Retrieve existing heuristic map results for a form."""
        supabase = get_supabase_client()
        result = (
            supabase.table("field_label_maps")
            .select("*")
            .eq("form_id", form_id)
            .eq("source", "heuristic")
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        return self._parse_map_rows(rows)

    def _parse_map_rows(self, rows: list[dict]) -> list[FieldLabelMap]:
        maps: list[FieldLabelMap] = []
        for row in rows:
            try:
                maps.append(FieldLabelMap(
                    id=row["id"],
                    form_id=row["form_id"],
                    field_id=row["field_id"],
                    field_name=row["field_name"],
                    label_text=row.get("label_text"),
                    semantic_key=row.get("semantic_key"),
                    confidence=int(row.get("confidence", 0)),
                    source=row.get("source", "auto"),
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                ))
            except Exception as e:
                logger.warning("Failed to parse field_label_map row %s: %s", row.get("id"), e)
        return maps

    def list_by_form(self, form_id: str, created_at: str | None = None) -> list[FieldLabelMap]:
        """Return maps for a form. If created_at is given, return that run; otherwise return the latest run."""
        supabase = get_supabase_client()
        if created_at:
            result = (
                supabase.table("field_label_maps")
                .select("*")
                .eq("form_id", form_id)
                .eq("created_at", created_at)
                .execute()
            )
            return self._parse_map_rows(result.data if hasattr(result, "data") else [])

        # Fetch all rows ordered by created_at desc, filter to latest run client-side
        result = (
            supabase.table("field_label_maps")
            .select("*")
            .eq("form_id", form_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        if not rows:
            return []
        latest_ts = rows[0]["created_at"]
        return self._parse_map_rows([r for r in rows if r.get("created_at") == latest_ts])

    def list_runs(self, form_id: str) -> list[MapRun]:
        """Return one summary per past run, newest first."""
        supabase = get_supabase_client()
        result = (
            supabase.table("field_label_maps")
            .select("created_at, label_text")
            .eq("form_id", form_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []

        # Group by created_at
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)
        for row in rows:
            ts = row.get("created_at")
            if ts:
                groups[ts].append(row)

        runs: list[MapRun] = []
        for ts in sorted(groups.keys(), reverse=True):
            group = groups[ts]
            runs.append(MapRun(
                created_at=datetime.fromisoformat(ts),
                field_count=len(group),
                identified_count=sum(1 for r in group if r.get("label_text")),
            ))
        return runs


class MessageService:
    """Persists and retrieves activity log entries for a conversation."""

    def add(self, conversation_id: str, role: str, content: str) -> Message:
        msg = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        supabase = get_supabase_client()
        supabase.table("messages").insert({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }).execute()
        return msg

    def list_by_conversation(self, conversation_id: str) -> list[Message]:
        supabase = get_supabase_client()
        result = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        messages: list[Message] = []
        for row in rows:
            try:
                messages.append(Message(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                ))
            except Exception as e:
                logger.warning("Failed to parse message row %s: %s", row.get("id"), e)
        return messages


class FormRulesService:
    """Manages the global form_rules table (one row per form)."""

    def upsert(
        self,
        form_id: str,
        rule_items: list[RuleItem],
        description: str | None = None,
        rulebook_text: str | None = None,
        message_id: str | None = None,
    ) -> FormRules:
        """Create or update the global rules for a form."""
        supabase = get_supabase_client()
        existing = self.get(form_id)

        rules_json = [r.model_dump() for r in rule_items]
        now = datetime.now(timezone.utc).isoformat()

        if existing:
            payload: dict = {
                "rules": rules_json,
                "updated_at": now,
            }
            if description is not None:
                payload["description"] = description
            if rulebook_text is not None:
                payload["rulebook_text"] = rulebook_text
            if message_id is not None:
                payload["message_id"] = message_id
            supabase.table("form_rules").update(payload).eq("form_id", form_id).execute()
            return FormRules(
                id=existing.id,
                form_id=form_id,
                description=description if description is not None else existing.description,
                rulebook_text=rulebook_text if rulebook_text is not None else existing.rulebook_text,
                rules=rule_items,
                message_id=message_id or existing.message_id,
            )

        row_id = str(uuid4())
        supabase.table("form_rules").insert({
            "id": row_id,
            "form_id": form_id,
            "description": description,
            "rulebook_text": rulebook_text,
            "rules": rules_json,
            "message_id": message_id,
            "created_at": now,
            "updated_at": now,
        }).execute()

        return FormRules(
            id=row_id,
            form_id=form_id,
            description=description,
            rulebook_text=rulebook_text,
            rules=rule_items,
            message_id=message_id,
        )

    def get(self, form_id: str) -> FormRules | None:
        """Read the global rules for a form."""
        supabase = get_supabase_client()
        result = (
            supabase.table("form_rules")
            .select("*")
            .eq("form_id", form_id)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        if not rows:
            return None
        row = rows[0]
        raw_rules = row.get("rules", [])
        rule_items: list[RuleItem] = []
        for r in raw_rules:
            try:
                rule_items.append(RuleItem(
                    type=RuleType(r.get("type", "format")),
                    rule_text=str(r.get("rule_text", "")),
                    field_ids=[str(fid) for fid in r.get("field_ids", [])],
                    question=r.get("question"),
                    options=[str(o) for o in r.get("options", [])],
                ))
            except Exception as e:
                logger.warning("Failed to parse form_rules rule: %s", e)
        return FormRules(
            id=row["id"],
            form_id=row["form_id"],
            description=row.get("description"),
            rulebook_text=row.get("rulebook_text"),
            rules=rule_items,
            message_id=row.get("message_id"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )


class FormSchemaService:
    """Manages the global form_schema table (one row per form, JSONB field array)."""

    _LABEL_PRIORITY = {"annotation": 0, "map_manual": 1, "map_auto": 2, "map_heuristic": 3, "pdf_extract": 4}

    def ensure_schema(self, form_id: str) -> FormSchema:
        """Seed form_schema row from PDF extraction if it does not exist.

        If a row already exists, return it as-is.
        """
        existing = self.get(form_id)
        if existing is not None:
            return existing

        form_service = FormService()
        fields, _text_blocks = form_service.get_fields_and_text_blocks(form_id)

        schema_fields = [
            FormSchemaField(
                field_id=f.id,
                field_name=f.name,
                field_type=f.field_type.value,
                bbox=f.bbox,
                page=f.page,
                default_value=f.value,
                label_text=f.name if f.name else None,
                label_source="pdf_extract" if f.name else None,
                options=f.options,
            )
            for f in fields
        ]

        supabase = get_supabase_client()
        row_id = str(uuid4())
        supabase.table("form_schema").insert({
            "id": row_id,
            "form_id": form_id,
            "schema": [sf.model_dump(mode="json") for sf in schema_fields],
        }).execute()

        return FormSchema(form_id=form_id, fields=schema_fields)

    def get(self, form_id: str) -> FormSchema | None:
        """Read the form schema for a given form."""
        supabase = get_supabase_client()
        result = (
            supabase.table("form_schema")
            .select("*")
            .eq("form_id", form_id)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        if not rows:
            return None
        row = rows[0]
        return self._parse_row(row)

    def upsert_from_annotation(self, form_id: str, annotation: Annotation) -> None:
        """Merge an annotation label into the schema (annotation always wins over map_auto)."""
        schema = self.get(form_id)
        if schema is None:
            schema = self.ensure_schema(form_id)

        found = False
        new_fields: list[FormSchemaField] = []
        for f in schema.fields:
            if f.field_id == annotation.field_id:
                found = True
                new_fields.append(FormSchemaField(
                    **{**f.model_dump(), **{
                        "label_text": annotation.label_text,
                        "label_source": "annotation",
                        "label_bbox": annotation.label_bbox,
                        "label_page": annotation.label_page,
                        "is_confirmed": True,
                    }}
                ))
            else:
                new_fields.append(f)

        if not found:
            new_fields.append(FormSchemaField(
                field_id=annotation.field_id,
                field_name=annotation.field_name,
                label_text=annotation.label_text,
                label_source="annotation",
                label_bbox=annotation.label_bbox,
                label_page=annotation.label_page,
                is_confirmed=True,
            ))

        self._save_schema(form_id, new_fields)

    def remove_annotation(self, form_id: str, field_id: str) -> None:
        """Revert a field's label to map fallback when its annotation is deleted."""
        schema = self.get(form_id)
        if schema is None:
            return

        # Check field_label_maps for fallback
        map_service = MapService()
        maps = map_service.list_by_form(form_id)
        fallback = next((m for m in maps if m.field_id == field_id), None)

        new_fields: list[FormSchemaField] = []
        for f in schema.fields:
            if f.field_id == field_id and f.label_source == "annotation":
                if fallback:
                    new_fields.append(FormSchemaField(
                        **{**f.model_dump(), **{
                            "label_text": fallback.label_text,
                            "label_source": "map_manual" if fallback.source == "manual" else "map_auto",
                            "label_bbox": None,
                            "label_page": None,
                            "semantic_key": fallback.semantic_key,
                            "confidence": fallback.confidence,
                            "is_confirmed": False,
                        }}
                    ))
                else:
                    new_fields.append(FormSchemaField(
                        **{**f.model_dump(), **{
                            "label_text": f.field_name if f.field_name else None,
                            "label_source": "pdf_extract" if f.field_name else None,
                            "label_bbox": None,
                            "label_page": None,
                            "is_confirmed": False,
                        }}
                    ))
            else:
                new_fields.append(f)

        self._save_schema(form_id, new_fields)

    def upsert_from_map(
        self,
        form_id: str,
        maps: list[FieldLabelMap],
        form_name: str | None = None,
    ) -> None:
        """Bulk update schema from a Map run. Only overwrites label if priority allows."""
        schema = self.get(form_id)
        if schema is None:
            schema = self.ensure_schema(form_id)

        existing_by_id = {f.field_id: f for f in schema.fields}

        for m in maps:
            existing = existing_by_id.get(m.field_id)
            source = "map_manual" if m.source == "manual" else ("map_heuristic" if m.source == "heuristic" else "map_auto")

            if existing is None:
                existing_by_id[m.field_id] = FormSchemaField(
                    field_id=m.field_id,
                    field_name=m.field_name,
                    label_text=m.label_text,
                    label_source=source,
                    semantic_key=m.semantic_key,
                    confidence=m.confidence,
                )
            else:
                current_priority = self._LABEL_PRIORITY.get(existing.label_source or "", 99)
                new_priority = self._LABEL_PRIORITY.get(source, 99)

                updates: dict = {
                    "semantic_key": m.semantic_key or existing.semantic_key,
                    "confidence": m.confidence,
                }
                # Only overwrite label if new source has equal or higher priority
                if new_priority <= current_priority:
                    updates["label_text"] = m.label_text or existing.label_text
                    updates["label_source"] = source

                existing_by_id[m.field_id] = FormSchemaField(
                    **{**existing.model_dump(), **updates}
                )

        new_fields = list(existing_by_id.values())
        self._save_schema(form_id, new_fields, form_name=form_name)

    def fill_values(self, form_id: str, values: dict[str, str]) -> FormSchema | None:
        """Write fill results back to form_schema by updating default_value on matched fields.

        Returns the updated FormSchema, or None if schema not found.
        """
        schema = self.get(form_id)
        if schema is None:
            return None

        updated_fields = [
            FormSchemaField(**{
                **f.model_dump(),
                "default_value": values.get(f.field_id, f.default_value),
            })
            for f in schema.fields
        ]
        self._save_schema(form_id, updated_fields, updated_by="fill")
        return FormSchema(
            form_id=schema.form_id,
            form_name=schema.form_name,
            form_rules_id=schema.form_rules_id,
            fields=updated_fields,
        )

    def link_rules(self, form_id: str, form_rules_id: str) -> None:
        """Set the form_rules_id FK on form_schema."""
        schema = self.get(form_id)
        if schema is None:
            self.ensure_schema(form_id)

        supabase = get_supabase_client()
        supabase.table("form_schema").update({
            "form_rules_id": form_rules_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("form_id", form_id).execute()

    def _save_schema(
        self,
        form_id: str,
        fields: list[FormSchemaField],
        form_name: str | None = None,
        updated_by: str | None = None,
        message_id: str | None = None,
    ) -> None:
        """Persist the schema JSONB array to the DB."""
        supabase = get_supabase_client()
        payload: dict = {
            "schema": [f.model_dump(mode="json") for f in fields],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if form_name is not None:
            payload["form_name"] = form_name
        if updated_by is not None:
            payload["updated_by"] = updated_by
        if message_id is not None:
            payload["message_id"] = message_id

        supabase.table("form_schema").update(payload).eq("form_id", form_id).execute()

    def _parse_row(self, row: dict) -> FormSchema:
        """Parse a DB row into a FormSchema model."""
        raw_schema = row.get("schema", [])
        fields: list[FormSchemaField] = []
        for item in raw_schema:
            try:
                bbox = _dict_to_bbox(item.get("bbox")) if item.get("bbox") else None
                label_bbox = _dict_to_bbox(item.get("label_bbox")) if item.get("label_bbox") else None
                fields.append(FormSchemaField(
                    field_id=item["field_id"],
                    field_name=item.get("field_name", ""),
                    field_type=item.get("field_type", "text"),
                    bbox=bbox,
                    page=item.get("page", 1),
                    default_value=item.get("default_value"),
                    label_text=item.get("label_text"),
                    label_source=item.get("label_source"),
                    label_bbox=label_bbox,
                    label_page=item.get("label_page"),
                    semantic_key=item.get("semantic_key"),
                    confidence=int(item.get("confidence", 0)),
                    is_confirmed=bool(item.get("is_confirmed", False)),
                    options=item.get("options", []),
                ))
            except Exception as e:
                logger.warning("Failed to parse form_schema field: %s", e)
        return FormSchema(
            form_id=row["form_id"],
            form_name=row.get("form_name"),
            form_rules_id=row.get("form_rules_id"),
            fields=fields,
        )


class FillService:
    """Drives the fill pipeline: build prompt, call OpenAI."""

    def __init__(self) -> None:
        self._conversation_service = ConversationService()
        self._annotation_service = AnnotationService()
        self._mapping_service = MappingService()
        self._map_service = MapService()
        self._context_service = ContextService()

    def _build_context(self, ctx: ContextWindow, ask_answers: dict[str, str] | None = None):
        """Gather all data and delegate to ContextService."""
        form_id = ctx.form_id or ""

        # Read from global form_schema (single source of truth)
        schema_service = FormSchemaService()
        schema = schema_service.get(form_id)

        if schema is not None:
            return self._context_service.build(
                schema_fields=schema.fields,
                user_info=ctx.user_info.data,
                rules=list(ctx.rules.items),
                ask_answers=ask_answers,
            )

        # Fallback: no form_schema yet, use legacy path
        form_service = FormService()
        fields, _text_blocks = form_service.get_fields_and_text_blocks(form_id)
        annotations = self._annotation_service.list_by_form(form_id)
        field_label_maps = self._map_service.list_by_form(form_id)
        mappings = self._mapping_service.list_by_conversation(ctx.conversation_id)

        return self._context_service.build_legacy(
            form_fields=fields,
            annotations=annotations,
            field_label_maps=field_label_maps,
            mappings=mappings,
            user_info=ctx.user_info.data,
            rules=list(ctx.rules.items),
            ask_answers=ask_answers,
        )

    def fill(
        self, conversation_id: str, ask_answers: dict[str, str] | None = None
    ) -> dict:
        """Run fill and return {fields: [{field_id, value}], ask: []}.

        ask_answers: resolved conditional question -> answer pairs from Ask mode.
        """
        settings = get_settings()

        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        ctx = self._conversation_service.get(conversation_id)
        if ctx is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        if not ctx.form_id:
            raise ValueError("No form associated with conversation")

        # Merge persisted answers with new request answers
        persisted = dict(ctx.ask_answers) if ctx.ask_answers else {}
        if ask_answers:
            persisted.update(ask_answers)
        ask_answers = persisted or None

        if ask_answers:
            self._conversation_service.update_ask_answers(conversation_id, ask_answers)

        # Check for unanswered conditional questions first
        unanswered = self._context_service.get_unanswered_questions(
            list(ctx.rules.items), ask_answers
        )
        if unanswered:
            return {
                "fields": [],
                "ask": [
                    {"question": r.question, "options": list(r.options)}
                    for r in unanswered
                    if r.question
                ],
            }

        fill_context = self._build_context(ctx, ask_answers)
        prompt, index_to_field_id = FillPrompt.build(fill_context)

        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        started_at = datetime.now(timezone.utc)
        prompt_log_id = _save_prompt_log(
            type="fill",
            prompt_template="FillPrompt",
            model=settings.openai_model,
            system_chars=len(prompt.system),
            user_chars=len(prompt.user),
            started_at=started_at,
            conversation_id=conversation_id,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
        )

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
        )

        _end_prompt_log(prompt_log_id, datetime.now(timezone.utc))

        content = response.choices[0].message.content or ""
        self._conversation_service.add_history_batch(conversation_id, [("user", prompt.user), ("agent", content)])

        filled = FillPrompt.parse(content, index_to_field_id)

        # Validate select/checkbox values against allowed options
        options_map = {f.field_id: f.options for f in fill_context.fields if f.options}
        checkbox_ids = {f.field_id for f in fill_context.fields if f.type == "checkbox"}
        validated: list[dict] = []
        for item in filled:
            fid = item["field_id"]
            val = item["value"]
            if fid in options_map:
                valid = options_map[fid]
                match = next((v for v in valid if v.lower() == val.lower()), None)
                if match:
                    validated.append({**item, "value": match})
                else:
                    logger.warning("Fill value %r not in options %s for field %s, skipping", val, valid, fid)
            elif fid in checkbox_ids:
                normalized = "true" if val.lower() in ("true", "yes", "1", "on") else "false"
                validated.append({**item, "value": normalized})
            else:
                validated.append(item)
        filled = validated

        if filled:
            values_map = {item["field_id"]: item["value"] for item in filled}
            self._conversation_service.update_form_values(conversation_id, values_map)

            # Write fill results back to form_schema
            form_id = ctx.form_id or ""
            schema_service = FormSchemaService()
            updated_schema = schema_service.fill_values(form_id, values_map)
            if updated_schema:
                return {
                    "fields": filled,
                    "ask": [],
                    "schema": updated_schema.model_dump(mode="json"),
                }

        return {"fields": filled, "ask": []}

    def ask(self, conversation_id: str) -> dict:
        """Return pre-classified conditional questions from the rulebook. No LLM call."""
        ctx = self._conversation_service.get(conversation_id)
        if ctx is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        ask_ctx = AskContext(rules=list(ctx.rules.items))
        prompt = AskPrompt.build(ask_ctx)
        parsed = json.loads(prompt.user)
        questions = [
            {"field_id": None, **q}
            for q in parsed["questions"]
        ]
        return {"questions": questions}

