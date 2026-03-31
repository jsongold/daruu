"""Tests for the simplified 3-file API (models, services, routes)."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import (
    Annotation,
    BBox,
    ContextWindow,
    CreateAnnotationRequest,
    FieldType,
    Form,
    FormField,
    HistoryMessage,
    Mapping,
    Mode,
    RuleItem,
    RuleType,
    Rules,
    TextBlock,
    UserInfo,
)
from app.services import AnnotationService, FormService, MappingService, ConversationService

client = TestClient(app)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestBBox:
    def test_construction(self):
        bbox = BBox(x=0.1, y=0.2, width=0.3, height=0.4)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.width == 0.3
        assert bbox.height == 0.4

    def test_frozen(self):
        bbox = BBox(x=0.0, y=0.0, width=1.0, height=1.0)
        with pytest.raises((ValidationError, TypeError)):
            bbox.x = 0.5  # type: ignore[misc]


class TestFormField:
    def test_construction_defaults(self):
        field = FormField(id="f1", name="name")
        assert field.field_type == FieldType.TEXT
        assert field.page == 1
        assert field.value is None
        assert field.bbox is None

    def test_frozen(self):
        field = FormField(id="f1", name="name")
        with pytest.raises((ValidationError, TypeError)):
            field.name = "other"  # type: ignore[misc]


class TestForm:
    def test_construction(self):
        form = Form(id="form1", document_id="doc1", page_count=3)
        assert form.fields == []
        assert form.page_count == 3

    def test_frozen(self):
        form = Form(id="form1", document_id="doc1")
        with pytest.raises((ValidationError, TypeError)):
            form.page_count = 5  # type: ignore[misc]


class TestAnnotation:
    def test_construction(self):
        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        ann = Annotation(
            document_id="doc1",
            label_text="Name",
            label_bbox=bbox,
            field_id="f1",
            field_name="name_field",
        )
        assert ann.document_id == "doc1"
        assert ann.label_text == "Name"
        assert ann.id is not None  # uuid generated

    def test_frozen(self):
        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        ann = Annotation(
            document_id="doc1",
            label_text="Name",
            label_bbox=bbox,
            field_id="f1",
            field_name="name_field",
        )
        with pytest.raises((ValidationError, TypeError)):
            ann.label_text = "Other"  # type: ignore[misc]


class TestMapping:
    def test_construction(self):
        m = Mapping(conversation_id="s1", annotation_id="a1", field_id="f1")
        assert m.confidence == 0.0
        assert m.reason == ""
        assert m.id is not None

    def test_frozen(self):
        m = Mapping(conversation_id="s1", annotation_id="a1", field_id="f1")
        with pytest.raises((ValidationError, TypeError)):
            m.confidence = 1.0  # type: ignore[misc]


class TestContextWindow:
    def test_construction_defaults(self):
        ctx = ContextWindow()
        assert ctx.mode == Mode.PREVIEW
        assert ctx.annotations == []
        assert ctx.mappings == []
        assert ctx.history == []
        assert ctx.conversation_id is not None

    def test_frozen(self):
        ctx = ContextWindow()
        with pytest.raises((ValidationError, TypeError)):
            ctx.mode = Mode.EDIT  # type: ignore[misc]


class TestModeEnum:
    def test_all_values(self):
        assert Mode.PREVIEW == "preview"
        assert Mode.EDIT == "edit"
        assert Mode.ANNOTATE == "annotate"
        assert Mode.FILL == "fill"
        assert Mode.ASK == "ask"


# ---------------------------------------------------------------------------
# DocumentService tests
# ---------------------------------------------------------------------------


def _make_supabase_mock():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return mock_client


class TestDocumentService:
    @patch("app.services.get_supabase_client")
    @patch("app.services.fitz")
    def test_upload_pdf_inserts_to_supabase(self, mock_fitz, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_fitz.open.return_value = mock_doc

        svc = DocumentService()
        with patch("app.services.Path.write_bytes"):
            form = svc.upload_pdf(b"%PDF-fake", "test.pdf")

        assert form.page_count == 2
        assert form.document_id is not None
        insert_call = mock_client.table.return_value.insert
        assert insert_call.called
        inserted_data = insert_call.call_args[0][0]
        assert "ref" in inserted_data
        assert inserted_data["document_type"] == "target"
        assert "meta" in inserted_data
        assert inserted_data["meta"]["filename"] == "test.pdf"

    @patch("app.services.fitz")
    def test_get_page_preview_raises_for_missing_doc(self, mock_fitz):
        svc = DocumentService()
        with patch("app.services.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                svc.get_page_preview_base64("nonexistent-id", 1)

    @patch("app.services.fitz")
    def test_get_fields_and_text_blocks_empty_doc(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_fitz.open.return_value = mock_doc

        svc = DocumentService()
        with patch("app.services.Path.exists", return_value=True):
            fields, text_blocks = svc.get_fields_and_text_blocks("some-doc-id")

        assert fields == []
        assert text_blocks == []


# ---------------------------------------------------------------------------
# AnnotationService tests
# ---------------------------------------------------------------------------


class TestAnnotationService:
    @patch("app.services.get_supabase_client")
    def test_create_inserts_with_confirmed_status(self, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        req = CreateAnnotationRequest(
            document_id="doc1",
            label_text="Name",
            label_bbox=bbox,
            field_id="f1",
            field_name="name_field",
        )
        svc = AnnotationService()
        annotation = svc.create(req)

        assert annotation.document_id == "doc1"
        insert_call = mock_client.table.return_value.insert
        assert insert_call.called
        inserted = insert_call.call_args[0][0]
        assert inserted["status"] == "confirmed"
        assert inserted["confidence"] == 100.0

    @patch("app.services.get_supabase_client")
    def test_list_by_document_returns_empty_when_no_data(self, mock_get_supabase):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_get_supabase.return_value = mock_client

        svc = AnnotationService()
        result = svc.list_by_document("doc1")
        assert result == []

    @patch("app.services.get_supabase_client")
    def test_delete_calls_supabase_delete(self, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        svc = AnnotationService()
        svc.delete("annotation-id-123")

        delete_chain = mock_client.table.return_value.delete.return_value.eq
        assert delete_chain.called
        assert delete_chain.call_args[0] == ("id", "annotation-id-123")


# ---------------------------------------------------------------------------
# ConversationService tests
# ---------------------------------------------------------------------------


class TestConversationService:
    @patch("app.services.get_supabase_client")
    def test_create_inserts_correct_fields_and_returns_context_window(self, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        svc = ConversationService()
        user_info = UserInfo(data={"name": "Alice"})
        rules = Rules(items=[RuleItem(type=RuleType.FORMAT, rule_text="rule1")])
        ctx = svc.create("doc1", user_info, rules)

        assert isinstance(ctx, ContextWindow)
        assert ctx.document_id == "doc1"
        assert ctx.mode == Mode.PREVIEW
        assert ctx.user_info.data == {"name": "Alice"}

        insert_call = mock_client.table.return_value.insert
        assert insert_call.called
        inserted = insert_call.call_args[0][0]
        assert inserted["document_id"] == "doc1"
        assert inserted["mode"] == Mode.PREVIEW.value
        assert "created_at" in inserted
        assert "updated_at" in inserted

    @patch("app.services.get_supabase_client")
    def test_get_returns_none_for_missing_session(self, mock_get_supabase):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_get_supabase.return_value = mock_client

        svc = ConversationService()
        result = svc.get("nonexistent-session")
        assert result is None

    @patch("app.services.get_supabase_client")
    def test_update_mode_calls_update_with_correct_value(self, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        svc = ConversationService()
        svc.update_mode("session-1", Mode.FILL)

        update_chain = mock_client.table.return_value.update
        assert update_chain.called
        update_data = update_chain.call_args[0][0]
        assert update_data["mode"] == Mode.FILL.value


# ---------------------------------------------------------------------------
# MappingService tests
# ---------------------------------------------------------------------------


class TestMappingService:
    @patch("app.services.get_supabase_client")
    def test_map_exact_match_creates_high_confidence_mapping(self, mock_get_supabase):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        field = FormField(id="f1", name="name", field_type=FieldType.TEXT, bbox=bbox, page=1)
        form = Form(id="form1", document_id="doc1", fields=[field], page_count=1)
        annotation = Annotation(
            id="ann1",
            document_id="doc1",
            label_text="name",
            label_bbox=bbox,
            field_id="f1",
            field_name="name",
        )

        svc = MappingService()
        mappings = svc.map("session1", form, [annotation])

        assert len(mappings) == 1
        assert mappings[0].field_id == "f1"
        assert mappings[0].confidence > 0.6

    @patch("app.config.get_settings")
    @patch("app.services.get_supabase_client")
    def test_map_no_match_no_mapping_when_openai_not_configured(
        self, mock_get_supabase, mock_settings
    ):
        mock_client = _make_supabase_mock()
        mock_get_supabase.return_value = mock_client

        settings = MagicMock()
        settings.openai_api_key = None
        mock_settings.return_value = settings

        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        field = FormField(id="f1", name="completely_different_xyz", bbox=bbox, page=1)
        form = Form(id="form1", document_id="doc1", fields=[field], page_count=1)
        annotation = Annotation(
            id="ann1",
            document_id="doc1",
            label_text="aaaaa",
            label_bbox=bbox,
            field_id="f1",
            field_name="aaaaa",
        )

        svc = MappingService()
        mappings = svc.map("session1", form, [annotation])

        assert mappings == []


# ---------------------------------------------------------------------------
# Route integration tests
# ---------------------------------------------------------------------------


class TestDocumentRoutes:
    @patch("app.routes.doc_service")
    def test_upload_document_returns_document_id_and_form(self, mock_doc_service):
        bbox = BBox(x=0.0, y=0.0, width=1.0, height=1.0)
        field = FormField(id="f1", name="name", bbox=bbox, page=1)
        form = Form(id="form1", document_id="doc123", fields=[field], page_count=1)
        mock_doc_service.upload_pdf.return_value = form

        pdf_bytes = b"%PDF-1.4 fake pdf content"
        response = client.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc123"
        assert "form" in data

    @patch("app.routes.doc_service")
    def test_get_document_fields_returns_fields_and_text_blocks(self, mock_doc_service):
        bbox = BBox(x=0.0, y=0.0, width=0.5, height=0.1)
        field = FormField(id="f1", name="name", bbox=bbox, page=1)
        text_block = TextBlock(id="t1", text="Hello", bbox=bbox, page=1)
        mock_doc_service.get_fields_and_text_blocks.return_value = ([field], [text_block])

        response = client.get("/api/documents/doc123/fields")

        assert response.status_code == 200
        data = response.json()
        assert len(data["fields"]) == 1
        assert len(data["text_blocks"]) == 1


class TestConversationRoutes:
    @patch("app.routes.conversation_service")
    def test_create_conversation_returns_conversation_id(self, mock_conversation_service):
        now = datetime.now(timezone.utc)
        ctx = ContextWindow(
            conversation_id="sess-abc",
            document_id="doc1",
            mode=Mode.PREVIEW,
            created_at=now,
            updated_at=now,
        )
        mock_conversation_service.create.return_value = ctx

        response = client.post(
            "/api/conversations",
            json={"document_id": "doc1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == "sess-abc"

    @patch("app.routes.conversation_service")
    def test_get_conversation_returns_404_for_missing(self, mock_conversation_service):
        mock_conversation_service.get.return_value = None

        response = client.get("/api/conversations/nonexistent")

        assert response.status_code == 404


class TestAnnotationRoutes:
    @patch("app.routes.annotation_service")
    def test_create_annotation_returns_annotation(self, mock_annotation_service):
        bbox = BBox(x=0.0, y=0.0, width=0.1, height=0.1)
        annotation = Annotation(
            id="ann1",
            document_id="doc1",
            label_text="Name",
            label_bbox=bbox,
            field_id="f1",
            field_name="name_field",
            created_at=datetime.now(timezone.utc),
        )
        mock_annotation_service.create.return_value = annotation

        response = client.post(
            "/api/annotations",
            json={
                "document_id": "doc1",
                "label_text": "Name",
                "label_bbox": {"x": 0.0, "y": 0.0, "width": 0.1, "height": 0.1},
                "field_id": "f1",
                "field_name": "name_field",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "ann1"

    @patch("app.routes.annotation_service")
    def test_delete_annotation_returns_204(self, mock_annotation_service):
        mock_annotation_service.delete.return_value = None

        response = client.delete("/api/annotations/ann1")

        assert response.status_code == 204
        mock_annotation_service.delete.assert_called_once_with("ann1")


class TestFillRoute:
    @patch("app.routes.fill_service")
    def test_fill_returns_sse_stream(self, mock_fill_service):
        from app.models import FillEvent

        async def _fake_stream(conversation_id, user_message=None):
            yield FillEvent(event="done", data={}).model_dump_json()

        mock_fill_service.fill_stream = _fake_stream

        response = client.post(
            "/api/fill",
            json={"conversation_id": "conv-1"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "done" in response.text
