"""Tests for document routes."""

import io

from fastapi.testclient import TestClient


class TestDocumentRoutes:
    """Tests for /documents endpoints."""

    def test_upload_source_document(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test uploading a source document."""
        response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "document_id" in data["data"]
        assert "document_ref" in data["data"]
        assert "meta" in data["data"]
        assert data["data"]["meta"]["filename"] == "test.pdf"
        assert data["data"]["meta"]["mime_type"] == "application/pdf"

    def test_upload_target_document(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test uploading a target document."""
        response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("form.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["meta"]["document_type"] == "target"

    def test_upload_no_file_fails(self, client: TestClient, api_prefix: str) -> None:
        """Test that upload without file fails."""
        response = client.post(
            f"{api_prefix}/documents",
            data={"document_type": "source"},
        )
        # Note: this API maps request validation errors to 400 (ApiResponse error envelope)
        assert response.status_code == 400

    def test_upload_invalid_type_fails(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that upload with invalid document type fails."""
        response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "invalid"},
        )
        # Note: this API maps request validation errors to 400 (ApiResponse error envelope)
        assert response.status_code == 400

    def test_upload_non_pdf_fails(self, client: TestClient, api_prefix: str) -> None:
        """Test that upload of non-PDF file fails."""
        response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")},
            data={"document_type": "source"},
        )
        assert response.status_code == 400

    def test_get_document(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test getting document metadata."""
        # First upload
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Then get
        response = client.get(f"{api_prefix}/documents/{document_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == document_id

    def test_get_document_not_found(self, client: TestClient, api_prefix: str) -> None:
        """Test getting non-existent document."""
        response = client.get(f"{api_prefix}/documents/non-existent-id")
        assert response.status_code == 404

    def test_get_page_preview(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test getting page preview."""
        # First upload
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get preview
        response = client.get(f"{api_prefix}/documents/{document_id}/pages/1/preview")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_get_page_preview_invalid_page(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test getting preview for invalid page number."""
        # First upload
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get preview for page 0 (invalid)
        response = client.get(f"{api_prefix}/documents/{document_id}/pages/0/preview")
        assert response.status_code == 400

    def test_get_page_preview_page_out_of_range(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test getting preview for page beyond document."""
        # First upload
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get preview for page 100 (likely beyond document)
        response = client.get(f"{api_prefix}/documents/{document_id}/pages/100/preview")
        assert response.status_code == 404
