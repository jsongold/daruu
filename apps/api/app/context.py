"""ContextService: resolves rules and builds filtered FillContext."""

import logging

from app.models import (
    Annotation,
    FieldLabelMap,
    FieldType,
    FillContext,
    FillField,
    FormField,
    FormSchemaField,
    Mapping,
    RuleItem,
    RuleType,
)

logger = logging.getLogger(__name__)


class ContextService:
    """Resolves rules against fields and builds a lean FillContext."""

    def build(
        self,
        schema_fields: list[FormSchemaField],
        user_info: dict[str, str],
        rules: list[RuleItem],
        ask_answers: dict[str, str] | None = None,
        general_rules: list[RuleItem] | None = None,
    ) -> FillContext:
        """Build FillContext from form_schema fields (rules pre-resolved).

        schema_fields come from the global form_schema table, already
        enriched with labels and semantic keys from annotate + map.

        general_rules are resolved from the general_rules table and
        stored on FillContext for system prompt injection.
        Form-level format rules override general format rules.
        """
        ask_answers = ask_answers or {}
        general_rules = general_rules or []

        skip_field_ids = self._resolve_skips(rules, ask_answers)

        fill_fields: list[FillField] = []

        for f in schema_fields:
            # Skip signature fields
            if f.field_type == "signature":
                continue

            # Skip already-filled fields
            if f.default_value is not None and f.default_value.strip():
                continue

            # Skip fields blocked by unresolved conditional rules
            if f.field_id in skip_field_ids:
                continue

            # Skip fields with no label and no name
            if not f.label_text and not f.field_name:
                continue

            # Skip fields with no meaningful label (confidence=0, not confirmed by annotation)
            if f.confidence == 0 and not f.is_confirmed:
                continue

            fill_fields.append(FillField(
                field_id=f.field_id,
                label=f.label_text or f.field_name,
                semantic_key=f.semantic_key,
                type=f.field_type,
                options=f.options,
                segment_title=f.segment_title,
            ))

        return FillContext(
            fields=fill_fields,
            user_info=user_info,
            general_rules=general_rules,
            form_rules=rules,
            ask_answers=ask_answers,
        )

    def build_legacy(
        self,
        form_fields: list[FormField],
        annotations: list[Annotation],
        field_label_maps: list[FieldLabelMap],
        mappings: list[Mapping],
        user_info: dict[str, str],
        rules: list[RuleItem],
        ask_answers: dict[str, str] | None = None,
    ) -> FillContext:
        """Legacy build path for backward compatibility.

        Converts old-style inputs to FormSchemaField list and delegates.
        """
        map_by_field = {m.field_id: m for m in field_label_maps}
        annotation_by_field = {a.field_id: a for a in annotations}

        schema_fields: list[FormSchemaField] = []
        for f in form_fields:
            flm = map_by_field.get(f.id)
            ann = annotation_by_field.get(f.id)

            label_text = None
            label_source = None
            semantic_key = None
            confidence = 0

            if ann:
                label_text = ann.label_text
                label_source = "annotation"
            if flm:
                label_text = label_text or flm.label_text
                label_source = label_source or ("map_manual" if flm.source == "manual" else "map_auto")
                semantic_key = flm.semantic_key
                confidence = flm.confidence

            if not label_text and f.name:
                label_text = f.name
                label_source = "pdf_extract"

            schema_fields.append(FormSchemaField(
                field_id=f.id,
                field_name=f.name,
                field_type=f.field_type.value,
                bbox=f.bbox,
                page=f.page,
                default_value=f.value,
                label_text=label_text,
                label_source=label_source,
                semantic_key=semantic_key,
                confidence=confidence,
                is_confirmed=ann is not None,
            ))

        return self.build(schema_fields, user_info, rules, ask_answers)

    def get_unanswered_questions(
        self,
        rules: list[RuleItem],
        ask_answers: dict[str, str] | None = None,
    ) -> list[RuleItem]:
        """Return conditional rules that still need user answers."""
        ask_answers = ask_answers or {}
        return [
            r for r in rules
            if r.type == RuleType.CONDITIONAL
            and r.question
            and r.question not in ask_answers
        ]

    def _resolve_skips(
        self,
        rules: list[RuleItem],
        ask_answers: dict[str, str],
    ) -> set[str]:
        """Determine which field_ids should be skipped based on rules.

        A field is skipped if:
        - It's governed by a conditional rule that is unanswered
        - It's governed by a conditional rule answered negatively
        """
        skip_ids: set[str] = set()

        for rule in rules:
            if rule.type != RuleType.CONDITIONAL:
                continue
            if not rule.question or not rule.field_ids:
                continue

            answer = ask_answers.get(rule.question)

            if answer is None:
                # Unanswered -> skip
                skip_ids.update(rule.field_ids)
            elif answer.lower() in ("no", "いいえ", "false", "0"):
                # Negative answer -> skip
                skip_ids.update(rule.field_ids)
            # Positive answer -> don't skip (fill these fields)

        return skip_ids

