"""StructuralResolver — Python-only field identification.

Resolves form field labels using:
1. Field ID semantics (e.g., ``employee_name`` -> "Employee Name")
2. Table structure detection via PyMuPDF ``page.find_tables()``

Fields resolved here skip LLM-based identification, reducing output tokens.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.domain.models.form_context import FormFieldSpec
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

_NON_SEMANTIC_PATTERN = re.compile(
    r"^(Text|Field|Check|Combo|List|Radio|Button|Signature)\d*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuralResolverResult:
    """Result of structural field resolution."""

    field_labels: dict[str, str] = field(default_factory=dict)
    unresolved_field_ids: tuple[str, ...] = ()
    confidence: dict[str, float] = field(default_factory=dict)
    resolution_method: dict[str, str] = field(default_factory=dict)


class StructuralResolver:
    """Resolves field labels using Python heuristics — no LLM needed.

    Resolution pipeline:
    1. ``resolve_field_ids`` — check if field_id itself is semantic
    2. ``resolve_by_table_structure`` — use PyMuPDF table detection
    """

    def __init__(self, document_service: DocumentService) -> None:
        self._document_service = document_service

    def resolve(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> StructuralResolverResult:
        """Run structural resolution pipeline.

        Args:
            document_id: Target document ID.
            fields: Form field specifications.

        Returns:
            StructuralResolverResult with resolved labels and unresolved IDs.
        """
        field_labels: dict[str, str] = {}
        confidence: dict[str, float] = {}
        resolution_method: dict[str, str] = {}

        # Step 1: Resolve by field_id semantics
        id_resolved = self.resolve_field_ids(fields)
        field_labels.update(id_resolved["labels"])
        confidence.update(id_resolved["confidence"])
        for fid in id_resolved["labels"]:
            resolution_method[fid] = "field_id"

        # Step 2: Resolve remaining by table structure
        remaining = tuple(
            f for f in fields if f.field_id not in field_labels
        )
        if remaining:
            table_resolved = self.resolve_by_table_structure(document_id, remaining)
            field_labels.update(table_resolved["labels"])
            confidence.update(table_resolved["confidence"])
            for fid in table_resolved["labels"]:
                resolution_method[fid] = "table"

        unresolved = tuple(
            f.field_id for f in fields if f.field_id not in field_labels
        )

        return StructuralResolverResult(
            field_labels=field_labels,
            unresolved_field_ids=unresolved,
            confidence=confidence,
            resolution_method=resolution_method,
        )

    @staticmethod
    def resolve_field_ids(
        fields: tuple[FormFieldSpec, ...],
    ) -> dict[str, dict[str, str | float]]:
        """Check if field_id has semantic meaning.

        Semantic: ``employee_name``, ``companyAddress``, ``date_of_birth``
        Non-semantic: ``Text1``, ``Field3``, ``Check1``

        Returns:
            Dict with "labels" and "confidence" sub-dicts.
        """
        labels: dict[str, str] = {}
        conf: dict[str, float] = {}

        for f in fields:
            fid = f.field_id
            if _NON_SEMANTIC_PATTERN.match(fid):
                continue

            words = _split_field_id(fid)
            if len(words) >= 2:
                label = " ".join(w.capitalize() for w in words)
                labels[fid] = label
                conf[fid] = 0.8

        return {"labels": labels, "confidence": conf}

    def resolve_by_table_structure(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> dict[str, dict[str, str | float]]:
        """Resolve fields using PyMuPDF table detection.

        For each page with unresolved fields, detects tables and maps
        field bbox centers to table cells. Extracts column/row headers
        to build semantic labels.

        Returns:
            Dict with "labels" and "confidence" sub-dicts.
        """
        labels: dict[str, str] = {}
        conf: dict[str, float] = {}

        pdf_bytes = self._document_service.get_pdf_bytes(document_id)
        if pdf_bytes is None:
            logger.warning("No PDF bytes for table structure resolution: %s", document_id)
            return {"labels": labels, "confidence": conf}

        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF not available for table structure resolution")
            return {"labels": labels, "confidence": conf}

        # Group fields by page
        page_fields: dict[int, list[FormFieldSpec]] = {}
        for f in fields:
            if f.page is not None:
                page_fields.setdefault(f.page, []).append(f)

        if not page_fields:
            return {"labels": labels, "confidence": conf}

        # Get raw bboxes for field center lookup
        raw_bbox_map: dict[str, tuple[float, float]] = {}
        try:
            acroform = self._document_service.get_acroform_fields(document_id)
            if acroform:
                for af in acroform.fields:
                    if af.bbox:
                        cx = af.bbox.x + af.bbox.width / 2
                        cy = af.bbox.y + af.bbox.height / 2
                        raw_bbox_map[af.field_name] = (cx, cy)
        except Exception as e:
            logger.warning("Failed to get AcroForm for table resolution: %s", e)

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            for page_num, pfields in page_fields.items():
                if page_num < 1 or page_num > len(doc):
                    continue

                page = doc[page_num - 1]
                try:
                    tables = page.find_tables()
                except Exception as e:
                    logger.warning("Table detection failed for page %s: %s", page_num, e)
                    continue

                if not tables or not tables.tables:
                    continue

                for table in tables.tables:
                    extracted = table.extract()
                    if not extracted or len(extracted) < 2:
                        continue

                    header_row = extracted[0]
                    table_bbox = table.bbox  # (x0, y0, x1, y1)

                    for f in pfields:
                        if f.field_id in labels:
                            continue

                        center = raw_bbox_map.get(f.field_id)
                        if center is None:
                            continue

                        cx, cy = center

                        # Check if center is within table bounds
                        if not (table_bbox[0] <= cx <= table_bbox[2] and
                                table_bbox[1] <= cy <= table_bbox[3]):
                            continue

                        # Find which cell the center falls in
                        cell_info = _find_cell_for_point(table, cx, cy)
                        if cell_info is None:
                            continue

                        row_idx, col_idx = cell_info

                        col_header = (
                            header_row[col_idx].strip()
                            if col_idx < len(header_row) and header_row[col_idx]
                            else None
                        )

                        # Look for row section label (first column of this row)
                        row_section = None
                        if col_idx > 0 and row_idx < len(extracted):
                            first_cell = extracted[row_idx][0]
                            if first_cell and first_cell.strip():
                                row_section = first_cell.strip()

                        if col_header and row_section:
                            labels[f.field_id] = f"{row_section} > {col_header}"
                            conf[f.field_id] = 0.9
                        elif col_header:
                            labels[f.field_id] = col_header
                            conf[f.field_id] = 0.7
                        else:
                            conf[f.field_id] = 0.5

            doc.close()

        except Exception as e:
            logger.warning("Table structure resolution failed: %s", e)

        return {"labels": labels, "confidence": conf}


def _split_field_id(field_id: str) -> list[str]:
    """Split field_id into words by underscore, hyphen, or camelCase."""
    # First split by underscore/hyphen
    parts = re.split(r"[_\-]", field_id)
    words: list[str] = []
    for part in parts:
        # Split camelCase
        camel_words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)", part)
        if camel_words:
            words.extend(w.lower() for w in camel_words)
        elif part:
            words.append(part.lower())
    return words


def _find_cell_for_point(
    table: Any,
    x: float,
    y: float,
) -> tuple[int, int] | None:
    """Find which cell (row, col) a point falls into.

    Uses the table's cells attribute which contains cell bounding boxes.
    """
    try:
        cells = table.cells
        if not cells:
            return None

        # cells is a list of (x0, y0, x1, y1) tuples
        # Table is organized row-major
        col_count = table.col_count
        for idx, cell in enumerate(cells):
            cx0, cy0, cx1, cy1 = cell
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                row = idx // col_count
                col = idx % col_count
                return (row, col)
    except Exception:
        pass
    return None
