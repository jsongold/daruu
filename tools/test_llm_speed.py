"""LLM speed test — measures round-trip time, tokens, and latency with real DB data.

Uses litellm.success_callback to track token usage across all LLM calls,
including internal parallel calls made by LLMFieldEnricher.

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

import litellm

from app.domain.models.form_context import FormContext, FormFieldSpec
from app.infrastructure.repositories import (
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
)
from app.services.document_service import DocumentService
from app.services.fill_planner.planner import FillPlanner
from app.services.form_context import FormContextBuilder, LLMFieldEnricher, ProximityFieldEnricher
from app.services.llm.client import LiteLLMClient
from app.services.text_extraction_service import TextExtractionService
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    DETAILED_MODE_SYSTEM_PROMPT,
    build_autofill_prompt,
    build_detailed_prompt,
)


# ── Token tracker via litellm callback ──

_tracker = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "call_count": 0,
}


def _track_usage(kwargs, completion_response, start_time, end_time):
    """litellm success_callback — accumulates token usage."""
    usage = getattr(completion_response, "usage", None)
    if usage:
        _tracker["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        _tracker["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
    _tracker["call_count"] += 1


litellm.success_callback = [_track_usage]


def reset_tracker():
    _tracker["prompt_tokens"] = 0
    _tracker["completion_tokens"] = 0
    _tracker["call_count"] = 0


def get_tracker():
    return (
        _tracker["call_count"],
        _tracker["prompt_tokens"],
        _tracker["completion_tokens"],
    )


# ── Result row ──

class BenchRow:
    def __init__(self, name: str, latency_ms: int, calls: int,
                 prompt_tokens: int, completion_tokens: int):
        self.name = name
        self.latency_ms = latency_ms
        self.calls = calls
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


# ── Bench helper ──

async def bench(client: LiteLLMClient, name: str, system: str, user: str) -> BenchRow:
    prompt_chars = len(system) + len(user)
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"  prompt: {prompt_chars:,} chars")
    print(f"{'─' * 60}")

    reset_tracker()
    t0 = time.perf_counter()
    resp = await client.complete(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    calls, p_tok, c_tok = get_tracker()

    content = resp.content
    print(f"  time    : {elapsed_ms:,}ms")
    print(f"  tokens  : {p_tok:,} in + {c_tok:,} out = {p_tok + c_tok:,} total")
    print(f"  response: {len(content)} chars")
    try:
        parsed = json.loads(content)
        print(f"  keys    : {list(parsed.keys())}")
    except json.JSONDecodeError:
        print("  (not valid JSON)")
    print(f"  preview : {content[:300]}")

    return BenchRow(name, elapsed_ms, calls, p_tok, c_tok)


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

    # ── Initialize real services ──

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

    rows: list[BenchRow] = []

    # ── 1a: Context build — ProximityFieldEnricher (no LLM) ──

    print(f"\n{'─' * 60}")
    print("  Context build: ProximityFieldEnricher")
    print(f"{'─' * 60}")
    proximity_enricher = ProximityFieldEnricher(document_service=document_service)
    proximity_builder = FormContextBuilder(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        enricher=proximity_enricher,
    )

    t0 = time.perf_counter()
    context = await proximity_builder.build(
        document_id=document_id,
        conversation_id=conversation_id,
        field_hints=fields,
    )
    proximity_ms = int((time.perf_counter() - t0) * 1000)
    print(f"  time    : {proximity_ms:,}ms")
    print(f"  tokens  : 0 (no LLM calls)")
    print(f"  fields  : {len(context.fields)}, candidates: {len(context.mapping_candidates)}")

    rows.append(BenchRow("context (proximity)", proximity_ms, 0, 0, 0))

    # ── 1b: Context build — LLMFieldEnricher ──

    print(f"\n{'─' * 60}")
    print("  Context build: LLMFieldEnricher")
    print(f"{'─' * 60}")
    llm_enricher = LLMFieldEnricher(llm_client=client, document_service=document_service)
    llm_builder = FormContextBuilder(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        enricher=llm_enricher,
    )

    reset_tracker()
    t0 = time.perf_counter()
    llm_context = await llm_builder.build(
        document_id=document_id,
        conversation_id=conversation_id,
        field_hints=fields,
    )
    llm_enrich_ms = int((time.perf_counter() - t0) * 1000)
    calls, p_tok, c_tok = get_tracker()
    print(f"  time    : {llm_enrich_ms:,}ms")
    print(f"  tokens  : {p_tok:,} in + {c_tok:,} out = {p_tok + c_tok:,} total")
    print(f"  calls   : {calls}")
    print(f"  fields  : {len(llm_context.fields)}, candidates: {len(llm_context.mapping_candidates)}")

    rows.append(BenchRow("context (LLM)", llm_enrich_ms, calls, p_tok, c_tok))

    # ── 2: Build prompts (using proximity context) ──

    fields_json, data_sources_text, user_rules = FillPlanner._prepare_prompt_inputs(context)
    print(f"\n  Prompt sizes: fields_json={len(fields_json):,} chars, data_sources={len(data_sources_text):,} chars")

    autofill_user = build_autofill_prompt(fields_json, data_sources_text, rules=user_rules)
    detailed_user = build_detailed_prompt(
        fields_json, data_sources_text,
        conversation_history="No previous conversation.",
        rules=user_rules,
        questions_asked=0,
    )

    # ── 3: Bench LLM calls ──

    rows.append(await bench(client, "Autofill (quick)", AUTOFILL_SYSTEM_PROMPT, autofill_user))
    rows.append(await bench(client, "Detailed turn", DETAILED_MODE_SYSTEM_PROMPT, detailed_user))

    # ── Summary table ──

    print(f"\n{'═' * 80}")
    print("  SUMMARY")
    print(f"{'═' * 80}")
    header = f"  {'Step':<25s} {'Latency':>8s} {'Calls':>6s} {'In Tok':>8s} {'Out Tok':>8s} {'Total':>8s}"
    print(header)
    print(f"  {'─' * 73}")

    total_ms = 0
    total_in = 0
    total_out = 0
    for r in rows:
        print(
            f"  {r.name:<25s} {r.latency_ms:>7,}ms {r.calls:>5d} "
            f"{r.prompt_tokens:>8,} {r.completion_tokens:>8,} {r.total_tokens:>8,}"
        )
        total_ms += r.latency_ms
        total_in += r.prompt_tokens
        total_out += r.completion_tokens

    print(f"  {'─' * 73}")
    print(
        f"  {'TOTAL':<25s} {total_ms:>7,}ms {'':>5s} "
        f"{total_in:>8,} {total_out:>8,} {total_in + total_out:>8,}"
    )


if __name__ == "__main__":
    asyncio.run(main())
