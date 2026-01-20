from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


def test_generate_returns_pdf() -> None:
    client = TestClient(app)
    schema_json = {
        "version": "v1",
        "name": "sample",
        "fields": [
            {
                "id": "name",
                "key": "name",
                "label": "Name",
                "type": "string",
                "required": True,
                "validation": {"min_length": 1},
                "placement": {
                    "page_index": 0,
                    "x": 72,
                    "y": 720,
                    "max_width": 240,
                    "align": "left",
                    "font_policy": {"size": 12, "min_size": 8},
                },
            },
            {
                "id": "address",
                "key": "address",
                "label": "Address",
                "type": "string",
                "required": True,
                "placement": {
                    "page_index": 0,
                    "x": 72,
                    "y": 700,
                    "max_width": 320,
                    "align": "left",
                    "font_policy": {"size": 12, "min_size": 8},
                },
            },
            {
                "id": "phone",
                "key": "phone",
                "label": "Phone",
                "type": "string",
                "required": False,
                "placement": {
                    "page_index": 0,
                    "x": 72,
                    "y": 680,
                    "max_width": 200,
                    "align": "left",
                    "font_policy": {"size": 12, "min_size": 8},
                },
            },
            {
                "id": "email",
                "key": "email",
                "label": "Email",
                "type": "string",
                "required": False,
                "placement": {
                    "page_index": 0,
                    "x": 72,
                    "y": 660,
                    "max_width": 260,
                    "align": "left",
                    "font_policy": {"size": 12, "min_size": 8},
                },
            },
            {
                "id": "notes",
                "key": "notes",
                "label": "Notes",
                "type": "string",
                "required": False,
                "placement": {
                    "page_index": 0,
                    "x": 72,
                    "y": 640,
                    "max_width": 360,
                    "align": "left",
                    "font_policy": {"size": 12, "min_size": 8},
                },
            },
        ],
    }
    response = client.post(
        "/generate",
        json={
            "schema_json": schema_json,
            "data": {
                "name": "山田太郎",
                "address": "東京都千代田区1-1",
                "phone": "03-0000-0000",
                "email": "taro@example.com",
                "notes": "備考がとても長い場合は自動的に縮小されます。",
            },
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    pdf_reader = PdfReader(BytesIO(response.content))
    assert len(pdf_reader.pages) >= 1
    assert len(response.content) > 100


def test_generate_rejects_invalid_schema() -> None:
    client = TestClient(app)
    response = client.post(
        "/generate",
        json={"schema_json": {"name": "broken"}, "data": {"name": "x"}},
    )

    assert response.status_code == 422
