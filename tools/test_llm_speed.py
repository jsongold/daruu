"""LLM speed test — measures round-trip time using actual prompts with real DB data.

Usage:
    PYTHONPATH=apps/api python tools/test_llm_speed.py <document_id> <conversation_id>

Example:
    PYTHONPATH=apps/api python tools/test_llm_speed.py abc123 conv456
"""

import asyncio
import json
import os
import sys
import time

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "infra", "docker-compose", ".env"))

from app.domain.models.form_context import FormContext, FormFieldSpec
from app.infrastructure.repositories import (
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
)
from app.services.document_service import DocumentService
from app.services.fill_planner.planner import FillPlanner
from app.services.form_context import FormContextBuilder, ProximityFieldEnricher
from app.services.llm.client import LiteLLMClient
from app.services.text_extraction_service import TextExtractionService
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    DETAILED_MODE_SYSTEM_PROMPT,
    build_autofill_prompt,
    build_detailed_prompt,
    format_data_sources,
)


# ── Bench helper ──

async def bench(client: LiteLLMClient, name: str, system: str, user: str) -> int:
    prompt_chars = len(system) + len(user)
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"  prompt: {prompt_chars:,} chars")
    print(f"{'─' * 60}")

    t0 = time.perf_counter()
    resp = await client.complete(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    content = resp.content
    print(f"  time    : {elapsed_ms}ms")
    print(f"  response: {len(content)} chars")
    try:
        parsed = json.loads(content)
        print(f"  keys    : {list(parsed.keys())}")
    except json.JSONDecodeError:
        print("  (not valid JSON)")
    print(f"  preview : {content[:300]}")

    return elapsed_ms


async def main():
    if len(sys.argv) < 3:
        print("Usage: PYTHONPATH=apps/api python tools/test_llm_speed.py <document_id> <conversation_id>")
        print("\nTo find IDs, check your Supabase DB or use a recent autofill request.")
        return

    document_id = sys.argv[1]
    conversation_id = sys.argv[2]

    client = LiteLLMClient()
    print(f"Model    : {client.model}")
    print(f"Available: {client.is_available}")
    if not client.is_available:
        print("ERROR: No API key. Set DARU_OPENAI_API_KEY or OPENAI_API_KEY.")
        return

    # ── Initialize real services (same as autofill_pipeline.py) ──

    data_source_repo = get_data_source_repository()
    doc_repo = get_document_repository()
    file_repo = get_file_repository()
    document_service = DocumentService(document_repository=doc_repo, file_repository=file_repo)
    extraction_service = TextExtractionService(
        data_source_repo=data_source_repo,
        document_service=document_service,
    )

    # ── Load real data from DB ──

    print(f"\nLoading data for document={document_id}, conversation={conversation_id}")

    data_sources = data_source_repo.list_by_conversation(conversation_id)
    print(f"  Data sources: {len(data_sources)}")
    for ds in data_sources:
        has_extracted = ds.extracted_data is not None
        print(f"    - {ds.name} ({ds.type.value}) extracted_data={'yes' if has_extracted else 'no'}")

    # Get fields from AcroForm
    acroform_response = document_service.get_acroform_fields(document_id)
    if not acroform_response or not acroform_response.fields:
        print("ERROR: No AcroForm fields found for this document.")
        return

    fields = tuple(
        FormFieldSpec(
            field_id=af.field_name,
            label=af.field_name,
            field_type=af.field_type or "text",
            page=af.bbox.page if af.bbox else None,
            x=af.bbox.x if af.bbox else None,
            y=af.bbox.y if af.bbox else None,
            width=af.bbox.width if af.bbox else None,
            height=af.bbox.height if af.bbox else None,
        )
        for af in acroform_response.fields
    )
    print(f"  Fields: {len(fields)}")

    # ── Step 1: Build real FormContext ──

    print("\nBuilding FormContext...")
    enricher = ProximityFieldEnricher(document_service=document_service)
    context_builder = FormContextBuilder(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        enricher=enricher,
    )

    t0 = time.perf_counter()
    context = await context_builder.build(
        document_id=document_id,
        conversation_id=conversation_id,
        field_hints=fields,
    )
    context_ms = int((time.perf_counter() - t0) * 1000)
    print(f"  Context build: {context_ms}ms")
    print(f"  Enriched fields: {len(context.fields)}")
    print(f"  Data source entries: {len(context.data_sources)}")
    print(f"  Mapping candidates: {len(context.mapping_candidates)}")

    # ── Step 2: Build real prompts using FillPlanner helpers ──

    fields_json, data_sources_text, user_rules = FillPlanner._prepare_prompt_inputs(context)

    print(f"\n  fields_json: {len(fields_json)} chars")
    print(f"  data_sources_text: {len(data_sources_text)} chars")

    autofill_user = build_autofill_prompt(fields_json, data_sources_text, rules=user_rules)
    detailed_user = build_detailed_prompt(
        fields_json, data_sources_text,
        conversation_history="No previous conversation.",
        rules=user_rules,
        questions_asked=0,
    )

    # ── Step 3: Bench each LLM call ──

    results: dict[str, int] = {}
    results["context_build"] = context_ms

    results["autofill_quick"] = await bench(
        client, "1. Autofill (quick mode)", AUTOFILL_SYSTEM_PROMPT, autofill_user,
    )
    results["detailed_turn"] = await bench(
        client, "2. Detailed mode turn", DETAILED_MODE_SYSTEM_PROMPT, detailed_user,
    )

    print(f"\n{'═' * 60}")
    print("  SUMMARY")
    print(f"{'═' * 60}")
    for name, ms in results.items():
        print(f"  {name:25s} {ms:>6d}ms")
    print(f"  {'total':25s} {sum(results.values()):>6d}ms")


if __name__ == "__main__":
    asyncio.run(main())
