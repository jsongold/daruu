#!/usr/bin/env python3
"""Quick-start: run the Daru PDF pipeline using app modules (in-process).

Edit the CONFIG section below, then run from the repository root:

    python tools/quick_start_pipeline.py

Requires app dependencies (e.g. from apps/api: pip install -e .).

This script imports and calls DocumentService, JobService, and related
models directly—no HTTP. Based on docs/TRAINING_GUIDE.md.
"""

import asyncio
import sys
from pathlib import Path

# Ensure apps/api is on the path so "app" resolves when run from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "apps" / "api"
if _API_DIR.exists() and str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

# -----------------------------------------------------------------------------
# CONFIG — edit these and run the script
# -----------------------------------------------------------------------------
MODE = "scratch"  # "transfer" or "scratch"
TARGET_PATH = _REPO_ROOT / "apps" / "tests" / "assets" / "2025bun_01_input.pdf"
# SOURCE_PATH = None  # e.g. Path("source.pdf") for transfer mode
OUTPUT_PATH = _REPO_ROOT / "tools" / "output.pdf"
RUN_MODE = "until_done"  # "until_blocked" or "until_done"


async def main() -> int:
    # Import app modules after path is set
    from app.models import DocumentType, JobCreate, JobMode, JobStatus, RunMode
    from app.services import DocumentService, JobService

    doc_service = DocumentService()
    job_service = JobService()

    # 1. Upload target (and source for transfer)
    print("Uploading target document...")
    target_content = TARGET_PATH.read_bytes()
    target_resp = await doc_service.upload_document(
        target_content,
        TARGET_PATH.name,
        DocumentType.TARGET,
    )
    target_doc_id = target_resp.document_id
    print(f"  target_document_id: {target_doc_id}")

    # 2. Create job
    print("Creating job...")
    create = JobCreate(
        mode=JobMode.SCRATCH,
        target_document_id=target_doc_id,
    )
    job = job_service.create_job(create)
    job_id = job.id
    print(f"  job_id: {job_id}")

    # 3. Run job (orchestrator runs pipeline in-process)
    print(RunMode.UNTIL_BLOCKED)
    run_mode = RunMode.UNTIL_BLOCKED if RUN_MODE == "until_blocked" else RunMode.UNTIL_DONE
    print(f"Running job (run_mode={run_mode.value})...")
    updated = await job_service.run_job(job_id, run_mode)
    status = updated.status
    print(f"  status: {status.value}")

    #     if status == JobStatus.DONE:
    #         # 4. Write output (MVP: target file path is the “output”)
    #         output_ref = Path(updated.target_document.ref)
    #         if output_ref.exists():
    #             OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    #             OUTPUT_PATH.write_bytes(output_ref.read_bytes())
    #             print(f"Output written to {OUTPUT_PATH}")
    #         else:
    #             print(f"warning: output file not found at {output_ref}", file=sys.stderr)
    #         print("Done.")
    #         return 0
    #     if status in (JobStatus.BLOCKED, JobStatus.AWAITING_INPUT):
    #         print(
    #             "Job is blocked and needs answers or edits. "
    #             "Use the API/UI to submit answers, then run the job again with until_done.",
    #             file=sys.stderr,
    #         )
    #         return 1
    #     print(f"Job ended with status: {status.value}", file=sys.stderr)
    #     return 1

    # except ValueError as e:
    #     print(f"Error: {e}", file=sys.stderr)
    #     return 1
    # except Exception as e:
    #     print(f"Error: {e}", file=sys.stderr)
    #     return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
