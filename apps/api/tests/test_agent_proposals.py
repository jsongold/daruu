"""Tests for agent proposal validation.

Tests the agent contracts and their proposal/response validation:
- FieldLabellingAgent: Links labels to field positions
- ValueExtractionAgent: Extracts and normalizes values
- MappingAgent: Maps source to target fields

Uses mock implementations to validate the contract interfaces.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from app.models import BBox, FieldModel, FieldType
from app.models.mapping import (
    FollowupQuestion,
    MappingItem,
    SourceField,
    TargetField,
)
# Agent protocol interfaces - imported for type reference only
# Actual implementations are mocked in tests
from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    EvidenceKind,
    LabelCandidate,
    LinkedField,
    StructureEvidence,
    TableCandidate,
    TextBlock,
)
from app.services.mapping.domain import MappingCandidate, MappingReason


# ============================================================================
# Mock Agent Implementations
# ============================================================================


class MockFieldLabellingAgent:
    """Mock implementation of FieldLabellingAgent protocol.

    Returns configurable linked fields for testing.
    """

    def __init__(
        self,
        linked_fields: list[LinkedField] | None = None,
        evidence: list[StructureEvidence] | None = None,
        confidence: float = 0.85,
        should_fail: bool = False,
    ):
        self.linked_fields = linked_fields or []
        self.evidence = evidence or []
        self.confidence = confidence
        self.should_fail = should_fail
        self.calls: list[dict] = []

    async def link_labels_to_boxes(
        self,
        page: int,
        page_image: bytes | None,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
        text_blocks: list[TextBlock],
        context: dict | None = None,
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Mock label-to-box linking."""
        self.calls.append({
            "page": page,
            "label_candidates": label_candidates,
            "box_candidates": box_candidates,
            "table_candidates": table_candidates,
            "text_blocks": text_blocks,
            "context": context,
        })

        if self.should_fail:
            raise RuntimeError("Mock agent failure")

        if self.linked_fields:
            return self.linked_fields, self.evidence

        # Auto-generate linked fields from candidates
        fields = []
        evidence_list = []

        for label, box in zip(label_candidates, box_candidates):
            field_id = f"field_{uuid4().hex[:8]}"
            evidence_id = f"ev_{uuid4().hex[:8]}"

            ev = StructureEvidence(
                id=evidence_id,
                kind=EvidenceKind.LLM_LINKING,
                field_id=field_id,
                document_id="test-doc",
                page=page,
                bbox=label.bbox,
                text=label.text,
                confidence=self.confidence,
                rationale=f"Mock linked {label.text} to box",
            )
            evidence_list.append(ev)

            linked = LinkedField(
                id=field_id,
                name=label.text,
                field_type="text",
                page=page,
                bbox=box.bbox,
                anchor_bbox=label.bbox,
                confidence=self.confidence,
                needs_review=self.confidence < 0.7,
                evidence_refs=(evidence_id,),
                label_candidate_id=label.id,
                box_candidate_id=box.id,
            )
            fields.append(linked)

        return fields, evidence_list


class MockValueExtractionAgent:
    """Mock implementation of ValueExtractionAgent protocol.

    Returns configurable extraction results for testing.
    """

    def __init__(
        self,
        value: str = "Sample Value",
        confidence: float = 0.9,
        conflict_detected: bool = False,
        should_fail: bool = False,
    ):
        self.value = value
        self.confidence = confidence
        self.conflict_detected = conflict_detected
        self.should_fail = should_fail
        self.calls: list[dict] = []

    async def extract_value(
        self,
        field: FieldModel,
        ocr_tokens: list[dict] | None = None,
        pdf_text: str | None = None,
        evidence: list[dict] | None = None,
    ) -> dict:
        """Mock value extraction."""
        self.calls.append({
            "field": field,
            "ocr_tokens": ocr_tokens,
            "pdf_text": pdf_text,
            "evidence": evidence,
        })

        if self.should_fail:
            raise RuntimeError("Mock extraction failure")

        return {
            "value_candidates": [
                {
                    "value": self.value,
                    "confidence": self.confidence,
                    "rationale": "Mock extraction",
                    "evidence_refs": [],
                }
            ],
            "normalized_value": self.value,
            "conflict_detected": self.conflict_detected,
            "followup_questions": [],
        }


class MockMappingAgent:
    """Mock implementation of MappingAgent protocol.

    Returns configurable mapping results for testing.
    """

    def __init__(
        self,
        confidence: float = 0.9,
        should_fail: bool = False,
        return_none: bool = False,
    ):
        self.confidence = confidence
        self.should_fail = should_fail
        self.return_none = return_none
        self.calls: list[dict] = []

    async def generate_mappings(
        self,
        source_fields: list[FieldModel],
        target_fields: list[FieldModel],
        template_history: list[dict] | None = None,
        user_rules: dict | None = None,
    ) -> dict:
        """Mock mapping generation."""
        self.calls.append({
            "source_fields": source_fields,
            "target_fields": target_fields,
            "template_history": template_history,
            "user_rules": user_rules,
        })

        if self.should_fail:
            raise RuntimeError("Mock mapping failure")

        if self.return_none:
            return {
                "mappings": [],
                "evidence_refs": [],
                "followup_questions": [],
            }

        # Generate mappings for matching fields
        mappings = []
        for src, tgt in zip(source_fields, target_fields):
            mappings.append({
                "source_field_id": src.id,
                "target_field_id": tgt.id,
                "confidence": self.confidence,
                "transform": None,
            })

        return {
            "mappings": mappings,
            "evidence_refs": [],
            "followup_questions": [],
        }


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_label_candidates():
    """Create sample label candidates."""
    return [
        LabelCandidate(
            id="label-1",
            text="Name",
            bbox=BBox(x=50, y=100, width=80, height=20, page=1),
            confidence=0.95,
            semantic_hints=["text"],
        ),
        LabelCandidate(
            id="label-2",
            text="Date",
            bbox=BBox(x=50, y=150, width=60, height=20, page=1),
            confidence=0.9,
            semantic_hints=["date"],
        ),
        LabelCandidate(
            id="label-3",
            text="Amount",
            bbox=BBox(x=50, y=200, width=70, height=20, page=1),
            confidence=0.88,
            semantic_hints=["number"],
        ),
    ]


@pytest.fixture
def sample_box_candidates():
    """Create sample box candidates."""
    return [
        BoxCandidate(
            id="box-1",
            box_type="text",
            bbox=BBox(x=150, y=100, width=200, height=25, page=1),
            confidence=0.9,
            has_border=True,
        ),
        BoxCandidate(
            id="box-2",
            box_type="date",
            bbox=BBox(x=150, y=150, width=120, height=25, page=1),
            confidence=0.85,
            has_border=True,
        ),
        BoxCandidate(
            id="box-3",
            box_type="text",
            bbox=BBox(x=150, y=200, width=100, height=25, page=1),
            confidence=0.8,
            has_border=True,
        ),
    ]


@pytest.fixture
def sample_field_model():
    """Create a sample field model."""
    return FieldModel(
        id=str(uuid4()),
        name="Test Field",
        field_type=FieldType.TEXT,
        value=None,
        confidence=None,
        bbox=BBox(x=100, y=200, width=200, height=30, page=1),
        document_id="test-doc",
        page=1,
        is_required=True,
        is_editable=True,
    )


@pytest.fixture
def sample_source_fields():
    """Create sample source fields for mapping."""
    return [
        FieldModel(
            id=str(uuid4()),
            name="Full Name",
            field_type=FieldType.TEXT,
            value="John Doe",
            confidence=0.95,
            bbox=BBox(x=100, y=100, width=200, height=30, page=1),
            document_id="source-doc",
            page=1,
            is_required=False,
            is_editable=False,
        ),
        FieldModel(
            id=str(uuid4()),
            name="Transaction Date",
            field_type=FieldType.DATE,
            value="2024-01-15",
            confidence=0.9,
            bbox=BBox(x=100, y=150, width=150, height=30, page=1),
            document_id="source-doc",
            page=1,
            is_required=False,
            is_editable=False,
        ),
    ]


@pytest.fixture
def sample_target_fields():
    """Create sample target fields for mapping."""
    return [
        FieldModel(
            id=str(uuid4()),
            name="Name",
            field_type=FieldType.TEXT,
            value=None,
            confidence=None,
            bbox=BBox(x=100, y=100, width=200, height=30, page=1),
            document_id="target-doc",
            page=1,
            is_required=True,
            is_editable=True,
        ),
        FieldModel(
            id=str(uuid4()),
            name="Date",
            field_type=FieldType.DATE,
            value=None,
            confidence=None,
            bbox=BBox(x=100, y=150, width=150, height=30, page=1),
            document_id="target-doc",
            page=1,
            is_required=True,
            is_editable=True,
        ),
    ]


# ============================================================================
# FieldLabellingAgent Tests
# ============================================================================


class TestFieldLabellingAgentProposals:
    """Test FieldLabellingAgent contract validation."""

    @pytest.mark.asyncio
    async def test_returns_linked_fields(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test agent returns linked fields for label-box pairs."""
        agent = MockFieldLabellingAgent(confidence=0.85)

        fields, evidence = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
            context=None,
        )

        assert len(fields) == min(
            len(sample_label_candidates), len(sample_box_candidates)
        )
        assert len(evidence) == len(fields)

    @pytest.mark.asyncio
    async def test_linked_field_has_required_attributes(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test that linked fields have all required attributes."""
        agent = MockFieldLabellingAgent(confidence=0.9)

        fields, _ = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
        )

        for field in fields:
            assert field.id is not None
            assert field.name is not None
            assert field.field_type is not None
            assert field.page == 1
            assert field.bbox is not None
            assert field.confidence is not None
            assert 0.0 <= field.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_evidence_references_field(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test that evidence correctly references field."""
        agent = MockFieldLabellingAgent()

        fields, evidence = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
        )

        field_ids = {f.id for f in fields}
        for ev in evidence:
            assert ev.field_id in field_ids

    @pytest.mark.asyncio
    async def test_low_confidence_marks_needs_review(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test that low confidence fields are marked for review."""
        agent = MockFieldLabellingAgent(confidence=0.5)  # Below threshold

        fields, _ = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
        )

        for field in fields:
            assert field.needs_review is True

    @pytest.mark.asyncio
    async def test_high_confidence_not_marked_for_review(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test that high confidence fields are not marked for review."""
        agent = MockFieldLabellingAgent(confidence=0.95)

        fields, _ = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
        )

        for field in fields:
            assert field.needs_review is False

    @pytest.mark.asyncio
    async def test_handles_empty_candidates(self):
        """Test agent handles empty candidate lists."""
        agent = MockFieldLabellingAgent()

        fields, evidence = await agent.link_labels_to_boxes(
            page=1,
            page_image=None,
            label_candidates=[],
            box_candidates=[],
            table_candidates=[],
            text_blocks=[],
        )

        assert fields == []
        assert evidence == []

    @pytest.mark.asyncio
    async def test_records_call_details(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test that agent records call details for auditing."""
        agent = MockFieldLabellingAgent()

        await agent.link_labels_to_boxes(
            page=1,
            page_image=b"fake_image",
            label_candidates=sample_label_candidates,
            box_candidates=sample_box_candidates,
            table_candidates=[],
            text_blocks=[],
            context={"document_type": "invoice"},
        )

        assert len(agent.calls) == 1
        assert agent.calls[0]["page"] == 1
        assert agent.calls[0]["label_candidates"] == sample_label_candidates
        assert agent.calls[0]["context"] == {"document_type": "invoice"}


# ============================================================================
# ValueExtractionAgent Tests
# ============================================================================


class TestValueExtractionAgentProposals:
    """Test ValueExtractionAgent contract validation."""

    @pytest.mark.asyncio
    async def test_returns_value_candidates(self, sample_field_model):
        """Test agent returns value candidates."""
        agent = MockValueExtractionAgent(value="John Doe", confidence=0.95)

        result = await agent.extract_value(
            field=sample_field_model,
            ocr_tokens=None,
            pdf_text="Sample text",
        )

        assert "value_candidates" in result
        assert len(result["value_candidates"]) >= 1
        assert result["value_candidates"][0]["value"] == "John Doe"

    @pytest.mark.asyncio
    async def test_returns_normalized_value(self, sample_field_model):
        """Test agent returns normalized value."""
        agent = MockValueExtractionAgent(value="2024-01-15")

        result = await agent.extract_value(field=sample_field_model)

        assert "normalized_value" in result
        assert result["normalized_value"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_detects_conflicts(self, sample_field_model):
        """Test agent reports conflict detection."""
        agent = MockValueExtractionAgent(conflict_detected=True)

        result = await agent.extract_value(field=sample_field_model)

        assert result["conflict_detected"] is True

    @pytest.mark.asyncio
    async def test_includes_confidence_score(self, sample_field_model):
        """Test that value candidates include confidence scores."""
        agent = MockValueExtractionAgent(confidence=0.85)

        result = await agent.extract_value(field=sample_field_model)

        for candidate in result["value_candidates"]:
            assert "confidence" in candidate
            assert 0.0 <= candidate["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_uses_ocr_tokens_when_provided(self, sample_field_model):
        """Test agent uses OCR tokens when provided."""
        agent = MockValueExtractionAgent()
        ocr_tokens = [
            {"text": "John", "bbox": [100, 200, 50, 20], "confidence": 0.9},
            {"text": "Doe", "bbox": [155, 200, 40, 20], "confidence": 0.85},
        ]

        await agent.extract_value(
            field=sample_field_model,
            ocr_tokens=ocr_tokens,
        )

        assert len(agent.calls) == 1
        assert agent.calls[0]["ocr_tokens"] == ocr_tokens

    @pytest.mark.asyncio
    async def test_uses_pdf_text_when_provided(self, sample_field_model):
        """Test agent uses PDF text when provided."""
        agent = MockValueExtractionAgent()
        pdf_text = "This is extracted PDF text"

        await agent.extract_value(
            field=sample_field_model,
            pdf_text=pdf_text,
        )

        assert agent.calls[0]["pdf_text"] == pdf_text


# ============================================================================
# MappingAgent Tests
# ============================================================================


class TestMappingAgentProposals:
    """Test MappingAgent contract validation."""

    @pytest.mark.asyncio
    async def test_returns_mappings(
        self, sample_source_fields, sample_target_fields
    ):
        """Test agent returns mappings for fields."""
        agent = MockMappingAgent(confidence=0.9)

        result = await agent.generate_mappings(
            source_fields=sample_source_fields,
            target_fields=sample_target_fields,
        )

        assert "mappings" in result
        assert len(result["mappings"]) >= 1

    @pytest.mark.asyncio
    async def test_mapping_has_required_attributes(
        self, sample_source_fields, sample_target_fields
    ):
        """Test mappings have required attributes."""
        agent = MockMappingAgent()

        result = await agent.generate_mappings(
            source_fields=sample_source_fields,
            target_fields=sample_target_fields,
        )

        for mapping in result["mappings"]:
            assert "source_field_id" in mapping
            assert "target_field_id" in mapping
            assert "confidence" in mapping
            assert 0.0 <= mapping["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_matches(
        self, sample_source_fields, sample_target_fields
    ):
        """Test agent returns empty mappings when no matches found."""
        agent = MockMappingAgent(return_none=True)

        result = await agent.generate_mappings(
            source_fields=sample_source_fields,
            target_fields=sample_target_fields,
        )

        assert result["mappings"] == []

    @pytest.mark.asyncio
    async def test_uses_template_history(
        self, sample_source_fields, sample_target_fields
    ):
        """Test agent uses template history when provided."""
        agent = MockMappingAgent()
        template_history = [
            {"source": "Name", "target": "Full Name", "frequency": 10}
        ]

        await agent.generate_mappings(
            source_fields=sample_source_fields,
            target_fields=sample_target_fields,
            template_history=template_history,
        )

        assert agent.calls[0]["template_history"] == template_history

    @pytest.mark.asyncio
    async def test_uses_user_rules(
        self, sample_source_fields, sample_target_fields
    ):
        """Test agent uses user rules when provided."""
        agent = MockMappingAgent()
        user_rules = {"Name": "Full Name"}

        await agent.generate_mappings(
            source_fields=sample_source_fields,
            target_fields=sample_target_fields,
            user_rules=user_rules,
        )

        assert agent.calls[0]["user_rules"] == user_rules


# ============================================================================
# Agent Error Handling Tests
# ============================================================================


class TestAgentErrorHandling:
    """Test agent error handling."""

    @pytest.mark.asyncio
    async def test_field_labelling_agent_failure(
        self, sample_label_candidates, sample_box_candidates
    ):
        """Test handling of field labelling agent failure."""
        agent = MockFieldLabellingAgent(should_fail=True)

        with pytest.raises(RuntimeError, match="Mock agent failure"):
            await agent.link_labels_to_boxes(
                page=1,
                page_image=None,
                label_candidates=sample_label_candidates,
                box_candidates=sample_box_candidates,
                table_candidates=[],
                text_blocks=[],
            )

    @pytest.mark.asyncio
    async def test_value_extraction_agent_failure(self, sample_field_model):
        """Test handling of value extraction agent failure."""
        agent = MockValueExtractionAgent(should_fail=True)

        with pytest.raises(RuntimeError, match="Mock extraction failure"):
            await agent.extract_value(field=sample_field_model)

    @pytest.mark.asyncio
    async def test_mapping_agent_failure(
        self, sample_source_fields, sample_target_fields
    ):
        """Test handling of mapping agent failure."""
        agent = MockMappingAgent(should_fail=True)

        with pytest.raises(RuntimeError, match="Mock mapping failure"):
            await agent.generate_mappings(
                source_fields=sample_source_fields,
                target_fields=sample_target_fields,
            )


# ============================================================================
# Agent Protocol Compliance Tests
# ============================================================================


class TestAgentProtocolCompliance:
    """Test that mock agents comply with protocol interfaces."""

    def test_field_labelling_agent_protocol(self):
        """Verify MockFieldLabellingAgent implements the protocol."""
        agent = MockFieldLabellingAgent()
        # Check required method exists with correct signature
        assert hasattr(agent, "link_labels_to_boxes")
        assert callable(agent.link_labels_to_boxes)

    def test_value_extraction_agent_protocol(self):
        """Verify MockValueExtractionAgent implements the protocol."""
        agent = MockValueExtractionAgent()
        assert hasattr(agent, "extract_value")
        assert callable(agent.extract_value)

    def test_mapping_agent_protocol(self):
        """Verify MockMappingAgent implements the protocol."""
        agent = MockMappingAgent()
        assert hasattr(agent, "generate_mappings")
        assert callable(agent.generate_mappings)
