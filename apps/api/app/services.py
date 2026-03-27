"""Business logic services: DocumentService, AnnotationService, SessionService, MappingService, MapService, FillService."""

import base64
import difflib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import fitz  # PyMuPDF
from app.config import get_settings
from app.infrastructure.supabase.client import get_supabase_client
from app.context import ContextService
from app.prompts import (
    FILL_SYSTEM_PROMPT,
    MAP_SYSTEM_PROMPT,
    UNDERSTAND_SYSTEM_PROMPT,
    build_fill_prompt,
    build_fill_prompt_v2,
    build_map_prompt,
    build_understand_prompt,
)
from app.models import (
    Annotation,
    BBox,
    Conversation,
    ContextWindow,
    CreateAnnotationRequest,
    FieldLabelMap,
    FieldType,
    Form,
    FormField,
    HistoryMessage,
    MapResult,
    MapRun,
    Mapping,
    Mode,
    RuleItem,
    RuleType,
    Rules,
    TextBlock,
    UserInfo,
)

logger = logging.getLogger(__name__)

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


class DocumentService:
    """Handles PDF upload, preview, and field extraction."""

    def upload_pdf(self, file_bytes: bytes, filename: str) -> Form:
        settings = get_settings()
        doc_id = str(uuid4())
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{doc_id}.pdf"
        file_path.write_bytes(file_bytes)

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        fields = self._extract_fields(doc, doc_id)
        doc.close()

        supabase = get_supabase_client()
        supabase.table("documents").insert(
            {
                "id": doc_id,
                "ref": str(file_path),
                "document_type": "target",
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
            document_id=doc_id,
            fields=fields,
            page_count=page_count,
        )
        return form

    def _extract_fields(self, doc: fitz.Document, document_id: str) -> list[FormField]:
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
                fields.append(
                    FormField(
                        id=str(uuid4()),
                        name=widget.field_name or f"field_{len(fields)}",
                        field_type=_to_field_type(widget.field_type_string or ""),
                        bbox=bbox,
                        page=page_num,
                        value=widget.field_value if isinstance(widget.field_value, str) else None,
                    )
                )
        return fields

    def _get_file_path(self, document_id: str) -> Path:
        settings = get_settings()
        return Path(settings.upload_dir) / f"{document_id}.pdf"

    def get_page_count(self, document_id: str) -> int:
        file_path = self._get_file_path(document_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Document {document_id} not found")
        doc = fitz.open(str(file_path))
        count = len(doc)
        doc.close()
        return count

    def get_page_preview_base64(self, document_id: str, page: int) -> str:
        file_path = self._get_file_path(document_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Document {document_id} not found")

        doc = fitz.open(str(file_path))
        if page < 1 or page > len(doc):
            doc.close()
            raise ValueError(f"Page {page} out of range for document {document_id}")

        pdf_page = doc[page - 1]
        mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
        pix = pdf_page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        doc.close()

        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def get_fields_and_text_blocks(
        self, document_id: str
    ) -> tuple[list[FormField], list[TextBlock]]:
        file_path = self._get_file_path(document_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Document {document_id} not found")

        doc = fitz.open(str(file_path))
        fields = self._extract_fields(doc, document_id)
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
    """CRUD for annotation pairs stored in Supabase."""

    def create(self, req: CreateAnnotationRequest) -> Annotation:
        annotation = Annotation(
            id=str(uuid4()),
            document_id=req.document_id,
            label_text=req.label_text,
            label_bbox=req.label_bbox,
            label_page=req.label_page,
            field_id=req.field_id,
            field_name=req.field_name,
            field_bbox=req.field_bbox,
            field_page=req.field_page,
            created_at=datetime.now(timezone.utc),
        )

        supabase = get_supabase_client()
        supabase.table("annotation_pairs").insert(
            {
                "id": annotation.id,
                "document_id": annotation.document_id,
                "label_id": annotation.id,
                "label_text": annotation.label_text,
                "label_bbox": _bbox_to_dict(annotation.label_bbox),
                "label_page": annotation.label_page,
                "field_id": annotation.field_id,
                "field_name": annotation.field_name,
                "field_bbox": _bbox_to_dict(annotation.field_bbox),
                "field_page": annotation.field_page,
                "confidence": 100.0,
                "status": "confirmed",
                "is_manual": True,
                "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
            }
        ).execute()

        return annotation

    def list_by_document(self, document_id: str) -> list[Annotation]:
        supabase = get_supabase_client()
        result = (
            supabase.table("annotation_pairs")
            .select("*")
            .eq("document_id", document_id)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        annotations: list[Annotation] = []
        for row in rows:
            try:
                annotations.append(
                    Annotation(
                        id=row["id"],
                        document_id=row["document_id"],
                        label_text=row["label_text"],
                        label_bbox=BBox(**row["label_bbox"]),
                        label_page=row.get("label_page", 1),
                        field_id=row["field_id"],
                        field_name=row["field_name"],
                        field_bbox=_dict_to_bbox(row.get("field_bbox")),
                        field_page=row.get("field_page", 1),
                        created_at=datetime.fromisoformat(row["created_at"])
                        if row.get("created_at")
                        else None,
                    )
                )
            except Exception as e:
                logger.warning("Failed to parse annotation row %s: %s", row.get("id"), e)
        return annotations

    def delete(self, annotation_id: str) -> None:
        supabase = get_supabase_client()
        supabase.table("annotation_pairs").delete().eq("id", annotation_id).execute()


class SessionService:
    """Manages ContextWindow sessions in Supabase."""

    def create(self, document_id: str | None, user_info: UserInfo, rules: Rules) -> ContextWindow:
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        supabase = get_supabase_client()
        supabase.table("sessions").insert(
            {
                "id": session_id,
                "document_id": document_id,
                "user_info": user_info.model_dump(),
                "mode": Mode.PREVIEW.value,
                "history": [],
                "rules": rules.model_dump(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        ).execute()

        return ContextWindow(
            session_id=session_id,
            document_id=document_id,
            user_info=user_info,
            rules=rules,
            mode=Mode.PREVIEW,
            created_at=now,
            updated_at=now,
        )

    def get(self, session_id: str) -> ContextWindow | None:
        supabase = get_supabase_client()
        result = (
            supabase.table("sessions").select("*").eq("id", session_id).execute()
        )
        rows = result.data if hasattr(result, "data") else []
        if not rows:
            return None
        row = rows[0]

        try:
            user_info = UserInfo(**row.get("user_info", {}))
            rules = Rules(**row.get("rules", {"items": []}))
            history = [HistoryMessage(**m) for m in row.get("history", [])]

            return ContextWindow(
                session_id=row["id"],
                document_id=row.get("document_id"),
                user_info=user_info,
                rules=rules,
                rulebook_url=row.get("rulebook_url"),
                mode=Mode(row.get("mode", Mode.PREVIEW.value)),
                history=history,
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            )
        except Exception as e:
            logger.error("Failed to parse session %s: %s", session_id, e)
            return None

    def update_document(self, session_id: str, document_id: str) -> None:
        supabase = get_supabase_client()
        supabase.table("sessions").update(
            {"document_id": document_id, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", session_id).execute()

    def update_mode(self, session_id: str, mode: Mode) -> None:
        logger.info("Mode transition: session=%s mode=%s", session_id, mode.value)
        supabase = get_supabase_client()
        supabase.table("sessions").update(
            {"mode": mode.value, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", session_id).execute()

    def add_history(self, session_id: str, role: str, content: str) -> None:
        ctx = self.get(session_id)
        if ctx is None:
            logger.warning("Session %s not found for add_history", session_id)
            return
        updated = list(ctx.history) + [HistoryMessage(role=role, content=content)]
        supabase = get_supabase_client()
        supabase.table("sessions").update(
            {
                "history": [m.model_dump() for m in updated],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", session_id).execute()

    def update_user_info(self, session_id: str, data: dict) -> None:
        """Merge new key/value pairs into session user_info.data."""
        ctx = self.get(session_id)
        if ctx is None:
            return
        merged = {**ctx.user_info.data, **data}
        supabase = get_supabase_client()
        supabase.table("sessions").update(
            {"user_info": {"data": merged}, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", session_id).execute()

    def update_rules(self, session_id: str, rule_items: list["RuleItem"], rulebook_url: str | None = None) -> None:
        """Replace session rules with a new list of RuleItem objects."""
        supabase = get_supabase_client()
        payload: dict = {
            "rules": {"items": [i.model_dump() for i in rule_items]},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if rulebook_url is not None:
            payload["rulebook_url"] = rulebook_url
        supabase.table("sessions").update(payload).eq("id", session_id).execute()


class UnderstandService:
    """Analyzes a document and extracts filling rules via LLM."""

    def __init__(self) -> None:
        self._session_service = SessionService()
        self._document_service = DocumentService()

    def understand(self, session_id: str) -> None:
        """Run LLM analysis on the document and persist extracted rules to the session."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        ctx = self._session_service.get(session_id)
        if ctx is None:
            raise ValueError(f"Session {session_id} not found")
        if not ctx.document_id:
            raise ValueError("Session has no associated document")

        fields, text_blocks = self._document_service.get_fields_and_text_blocks(ctx.document_id)
        prompt = build_understand_prompt(fields, text_blocks)

        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": UNDERSTAND_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)

        rulebook_text: str = result.get("rulebook_text", "")
        raw_rules = result.get("rules", [])
        rule_items = [
            RuleItem(
                type=RuleType(r.get("type", "format")),
                rule_text=str(r.get("rule_text", "")),
                question=r.get("question") or None,
                options=[str(o) for o in r.get("options", [])],
            )
            for r in raw_rules
            if r.get("rule_text")
        ]

        rulebook_url: str | None = None
        if rulebook_text and ctx.document_id:
            try:
                supabase = get_supabase_client()
                key = f"{ctx.document_id}/rulebook.md"
                supabase.storage.from_("rulebooks").upload(
                    key,
                    rulebook_text.encode("utf-8"),
                    {"content-type": "text/markdown; charset=utf-8"},
                )
                rulebook_url = supabase.storage.from_("rulebooks").get_public_url(key)
            except Exception as e:
                logger.warning("Failed to upload rulebook to storage: %s", e)

        self._session_service.update_rules(session_id, rule_items, rulebook_url)


class MappingService:
    """Maps annotations to form fields using fuzzy matching + optional LLM fallback."""

    def map(
        self, session_id: str, form: Form, annotations: list[Annotation]
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
                    session_id=session_id,
                    annotation_id=annotation.id,
                    field_id=best_field.id,
                    confidence=best_ratio,
                    reason="fuzzy_match",
                )
                mappings.append(mapping)
            else:
                # Try LLM fallback if configured
                llm_mapping = self._llm_map(session_id, annotation, form)
                if llm_mapping:
                    mappings.append(llm_mapping)

        return mappings

    def _save_mapping(
        self,
        session_id: str,
        annotation_id: str,
        field_id: str,
        inferred_value: str | None = None,
        confidence: float = 0.0,
        reason: str = "",
    ) -> Mapping:
        mapping = Mapping(
            id=str(uuid4()),
            session_id=session_id,
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
                "session_id": mapping.session_id,
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
        self, session_id: str, annotation: Annotation, form: Form
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
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            result = json.loads(response.choices[0].message.content or "{}")
            matched_name = result.get("field_name")
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "llm_match")

            matched_field = next((f for f in form.fields if f.name == matched_name), None)
            if matched_field and confidence > 0.5:
                return self._save_mapping(
                    session_id=session_id,
                    annotation_id=annotation.id,
                    field_id=matched_field.id,
                    confidence=confidence,
                    reason=reason,
                )
        except Exception as e:
            logger.warning("LLM mapping failed for annotation %s: %s", annotation.id, e)

        return None

    def list_by_session(self, session_id: str) -> list[Mapping]:
        supabase = get_supabase_client()
        result = (
            supabase.table("form_mappings")
            .select("*")
            .eq("session_id", session_id)
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        mappings: list[Mapping] = []
        for row in rows:
            try:
                mappings.append(
                    Mapping(
                        id=row["id"],
                        session_id=row["session_id"],
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

    def run(self, document_id: str) -> list[FieldLabelMap]:
        """Run spatial candidate filtering + LLM to identify field labels, persist results."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        doc_service = DocumentService()
        fields, text_blocks = doc_service.get_fields_and_text_blocks(document_id)
        annotations = AnnotationService().list_by_document(document_id)

        prompt = build_map_prompt(fields, text_blocks, annotations)
        logger.info("Map prompt: document=%s fields=%d prompt_chars=%d", document_id, len(fields), len(prompt))

        from openai import OpenAI
        import time
        client = OpenAI(api_key=settings.openai_api_key)
        t0 = time.monotonic()
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": MAP_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=4096,
        )
        logger.info("Map LLM done: document=%s elapsed=%.1fs", document_id, time.monotonic() - t0)

        raw = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(raw)
            items = parsed.get("results", [])
        except Exception:
            items = []

        field_map = {f.id: f for f in fields}
        now = datetime.now(timezone.utc)
        results: list[FieldLabelMap] = []
        for item in items:
            field_id = item.get("field_id")
            if not field_id or field_id not in field_map:
                continue
            results.append(FieldLabelMap(
                id=str(uuid4()),
                document_id=document_id,
                field_id=field_id,
                field_name=field_map[field_id].name,
                label_text=item.get("label"),
                semantic_key=item.get("semantic_key"),
                confidence=int(item.get("confidence", 0)),
                source="auto",
                created_at=now,
            ))

        supabase = get_supabase_client()
        if results:
            supabase.table("field_label_maps").insert([
                {
                    "id": r.id,
                    "document_id": r.document_id,
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

        return results

    def _parse_map_rows(self, rows: list[dict]) -> list[FieldLabelMap]:
        maps: list[FieldLabelMap] = []
        for row in rows:
            try:
                maps.append(FieldLabelMap(
                    id=row["id"],
                    document_id=row["document_id"],
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

    def list_by_document(self, document_id: str, created_at: str | None = None) -> list[FieldLabelMap]:
        """Return maps for a document. If created_at is given, return that run; otherwise return the latest run."""
        supabase = get_supabase_client()
        if created_at:
            result = (
                supabase.table("field_label_maps")
                .select("*")
                .eq("document_id", document_id)
                .eq("created_at", created_at)
                .execute()
            )
            return self._parse_map_rows(result.data if hasattr(result, "data") else [])

        # Find the latest run's created_at, then fetch all rows for it
        latest = (
            supabase.table("field_label_maps")
            .select("created_at")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = latest.data if hasattr(latest, "data") else []
        if not rows:
            return []
        latest_ts = rows[0]["created_at"]
        result = (
            supabase.table("field_label_maps")
            .select("*")
            .eq("document_id", document_id)
            .eq("created_at", latest_ts)
            .execute()
        )
        return self._parse_map_rows(result.data if hasattr(result, "data") else [])

    def list_runs(self, document_id: str) -> list[MapRun]:
        """Return one summary per past run, newest first."""
        supabase = get_supabase_client()
        result = (
            supabase.table("field_label_maps")
            .select("created_at, label_text")
            .eq("document_id", document_id)
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


class ConversationService:
    """Persists and retrieves activity log entries for a session."""

    def add(self, session_id: str, role: str, content: str) -> Conversation:
        conv = Conversation(
            id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        supabase = get_supabase_client()
        supabase.table("conversations").insert({
            "id": conv.id,
            "session_id": conv.session_id,
            "role": conv.role,
            "content": conv.content,
            "created_at": conv.created_at.isoformat(),
        }).execute()
        return conv

    def list_by_session(self, session_id: str) -> list[Conversation]:
        supabase = get_supabase_client()
        result = (
            supabase.table("conversations")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        rows = result.data if hasattr(result, "data") else []
        convs: list[Conversation] = []
        for row in rows:
            try:
                convs.append(Conversation(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                ))
            except Exception as e:
                logger.warning("Failed to parse conversation row %s: %s", row.get("id"), e)
        return convs


class FillService:
    """Drives the fill pipeline: build prompt, call OpenAI."""

    def __init__(self) -> None:
        self._session_service = SessionService()
        self._annotation_service = AnnotationService()
        self._mapping_service = MappingService()
        self._map_service = MapService()
        self._context_service = ContextService()

    def _build_context(self, ctx: ContextWindow, user_message: str | None = None):
        """Gather all data and delegate to ContextService."""
        doc_id = ctx.document_id or ""
        doc_service = DocumentService()
        fields, text_blocks = doc_service.get_fields_and_text_blocks(doc_id)
        annotations = self._annotation_service.list_by_document(doc_id)
        field_label_maps = self._map_service.list_by_document(doc_id)
        mappings = self._mapping_service.list_by_session(ctx.session_id)

        return self._context_service.build(
            form_fields=fields,
            text_blocks=text_blocks,
            annotations=annotations,
            field_label_maps=field_label_maps,
            mappings=mappings,
            user_info=ctx.user_info.data,
            rules=list(ctx.rules.items),
            history=list(ctx.history),
            user_message=user_message,
        )

    def fill(
        self, session_id: str, user_message: str | None = None
    ) -> dict:
        """Run fill and return {fields: [{field_id, value}], ask: []}."""
        settings = get_settings()

        if not settings.openai_api_key:
            raise ValueError("OpenAI not configured")

        ctx = self._session_service.get(session_id)
        if ctx is None:
            raise ValueError(f"Session {session_id} not found")
        if not ctx.document_id:
            raise ValueError("No document associated with session")

        fill_context = self._build_context(ctx, user_message)
        prompt = build_fill_prompt_v2(fill_context)

        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        self._session_service.add_history(session_id, "user", prompt)

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": FILL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        self._session_service.add_history(session_id, "agent", content)

        result = json.loads(content)

        filled: list[dict] = []
        for item in result.get("fields", []):
            field_id = item.get("field_id")
            value = item.get("value")
            if field_id and value is not None:
                filled.append({"field_id": field_id, "value": str(value)})

        return {"fields": filled, "ask": []}

    def ask(self, session_id: str) -> dict:
        """Return pre-classified conditional questions from the rulebook. No LLM call."""
        ctx = self._session_service.get(session_id)
        if ctx is None:
            raise ValueError(f"Session {session_id} not found")

        questions = [
            {
                "field_id": None,
                "question": item.question,
                "options": list(item.options),
            }
            for item in ctx.rules.items
            if item.type == RuleType.CONDITIONAL and item.question
        ]
        return {"questions": questions}

