from __future__ import annotations

import os

from app.db.supabase import get_supabase_client


def _get_bucket_name() -> str:
    return os.getenv("SUPABASE_STORAGE_BUCKET", "pdfs")


def upload_pdf(*, path: str, pdf_bytes: bytes) -> None:
    client = get_supabase_client()
    bucket = client.storage.from_(_get_bucket_name())
    result = bucket.upload(
        path,
        pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(f"Failed to upload PDF to storage: {result['error']}")


def create_signed_download_url(*, path: str, expires_in: int = 3600) -> str:
    client = get_supabase_client()
    bucket = client.storage.from_(_get_bucket_name())
    result = bucket.create_signed_url(path, expires_in)
    if isinstance(result, dict):
        if result.get("error"):
            raise RuntimeError(f"Failed to create signed URL: {result['error']}")
        data = result.get("data") or {}
        signed_url = data.get("signedUrl") or result.get("signedUrl")
        if signed_url:
            return signed_url
    raise RuntimeError("Failed to create signed URL.")
