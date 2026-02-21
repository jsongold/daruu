from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.template_schema import DraftTemplate


def test_analyze_returns_schema_json(monkeypatch) -> None:
    monkeypatch.setenv("LLM_ANALYZE_MODE", "mock")
    client = TestClient(app)
    pdf_path = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "templates"
        / "sample-template.pdf"
    )
    with pdf_path.open("rb") as handle:
        response = client.post("/analyze", files={"file": ("sample.pdf", handle, "application/pdf")})

    assert response.status_code == 200
    payload = response.json()
    assert "schema_json" in payload
    DraftTemplate.model_validate(payload["schema_json"])


def test_analyze_requires_input() -> None:
    client = TestClient(app)
    response = client.post("/analyze")

    assert response.status_code == 400
