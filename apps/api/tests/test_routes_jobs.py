"""Tests for job routes."""

import io

import pytest
from fastapi.testclient import TestClient


class TestJobRoutes:
    """Tests for /jobs endpoints."""

    @pytest.fixture
    def uploaded_documents(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> dict[str, str]:
        """Upload source and target documents for job tests."""
        # Upload source document
        source_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("source.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "source"},
        )
        source_id = source_response.json()["data"]["document_id"]

        # Upload target document
        target_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("target.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        target_id = target_response.json()["data"]["document_id"]

        return {"source_id": source_id, "target_id": target_id}

    def test_create_transfer_job(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test creating a transfer job."""
        response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "transfer",
                "source_document_id": uploaded_documents["source_id"],
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data["data"]
        assert data["meta"]["mode"] == "transfer"

    def test_create_scratch_job(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test creating a scratch job."""
        response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["meta"]["mode"] == "scratch"

    def test_create_transfer_job_without_source_fails(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test that transfer job without source document fails."""
        response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "transfer",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        assert response.status_code == 400

    def test_create_job_with_invalid_document_fails(
        self,
        client: TestClient,
        api_prefix: str,
    ) -> None:
        """Test that job with non-existent document fails."""
        response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": "non-existent-id",
            },
        )
        assert response.status_code == 400

    def test_get_job(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test getting job context."""
        # Create job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Get job
        response = client.get(f"{api_prefix}/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == job_id
        assert data["data"]["status"] == "created"
        assert data["data"]["mode"] == "scratch"

    def test_get_job_not_found(self, client: TestClient, api_prefix: str) -> None:
        """Test getting non-existent job."""
        response = client.get(f"{api_prefix}/jobs/non-existent-id")
        assert response.status_code == 404

    def test_run_job_step(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test running a job in step mode."""
        # Create job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Run job
        response = client.post(
            f"{api_prefix}/jobs/{job_id}/run",
            json={"run_mode": "step"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "status" in data["data"]
        assert "job_context" in data["data"]

    def test_run_job_until_blocked(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test running a job until blocked."""
        # Create job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Run job
        response = client.post(
            f"{api_prefix}/jobs/{job_id}/run",
            json={"run_mode": "until_blocked"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should be blocked, awaiting input, or done
        assert data["data"]["status"] in ["blocked", "done", "awaiting_input"]

    def test_run_job_not_found(self, client: TestClient, api_prefix: str) -> None:
        """Test running non-existent job."""
        response = client.post(
            f"{api_prefix}/jobs/non-existent-id/run",
            json={"run_mode": "step"},
        )
        assert response.status_code == 404

    def test_submit_answers(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test submitting answers for a blocked job."""
        # Create and run job until blocked
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Run until blocked
        run_response = client.post(
            f"{api_prefix}/jobs/{job_id}/run",
            json={"run_mode": "until_blocked"},
        )

        # Get job to find field IDs
        job_response = client.get(f"{api_prefix}/jobs/{job_id}")
        job_data = job_response.json()["data"]
        fields = job_data["fields"]

        if fields:
            # Submit answer
            response = client.post(
                f"{api_prefix}/jobs/{job_id}/answers",
                json={"answers": [{"field_id": fields[0]["id"], "value": "Test Answer"}]},
            )
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_submit_edits(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test submitting manual edits."""
        # Create and run job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Run to generate fields
        client.post(f"{api_prefix}/jobs/{job_id}/run", json={"run_mode": "step"})

        # Get job to find field IDs
        job_response = client.get(f"{api_prefix}/jobs/{job_id}")
        fields = job_response.json()["data"]["fields"]

        if fields:
            # Submit edit
            response = client.post(
                f"{api_prefix}/jobs/{job_id}/edits",
                json={"edits": [{"field_id": fields[0]["id"], "value": "Edited Value"}]},
            )
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_get_review(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test getting job review."""
        # Create and run job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]
        client.post(f"{api_prefix}/jobs/{job_id}/run", json={"run_mode": "until_blocked"})

        # Get review
        response = client.get(f"{api_prefix}/jobs/{job_id}/review")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "issues" in data["data"]
        assert "previews" in data["data"]
        assert "fields" in data["data"]
        assert "confidence_summary" in data["data"]

    def test_get_activity(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test getting job activity log."""
        # Create job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Get activity
        response = client.get(f"{api_prefix}/jobs/{job_id}/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        # Should have at least the job_created activity
        assert len(data["data"]) >= 1
        assert data["data"][0]["action"] == "job_created"

    def test_get_evidence(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test getting evidence for a field."""
        # Create and run job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]
        client.post(f"{api_prefix}/jobs/{job_id}/run", json={"run_mode": "until_blocked"})

        # Get job to find field IDs
        job_response = client.get(f"{api_prefix}/jobs/{job_id}")
        fields = job_response.json()["data"]["fields"]

        if fields:
            # Get evidence
            response = client.get(
                f"{api_prefix}/jobs/{job_id}/evidence",
                params={"field_id": fields[0]["id"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "field_id" in data["data"]
            assert "evidence" in data["data"]

    def test_export_job(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test exporting job data as JSON."""
        # Create and run job
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]
        client.post(f"{api_prefix}/jobs/{job_id}/run", json={"run_mode": "until_blocked"})

        # Export
        response = client.get(f"{api_prefix}/jobs/{job_id}/export.json")
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert "mode" in data
        assert "status" in data
        assert "fields" in data
        assert "activities" in data

    def test_get_output_pdf_not_done_fails(
        self,
        client: TestClient,
        api_prefix: str,
        uploaded_documents: dict[str, str],
    ) -> None:
        """Test that getting output PDF for incomplete job fails."""
        # Create job (don't run to completion)
        create_response = client.post(
            f"{api_prefix}/jobs",
            json={
                "mode": "scratch",
                "target_document_id": uploaded_documents["target_id"],
            },
        )
        job_id = create_response.json()["data"]["job_id"]

        # Try to get output
        response = client.get(f"{api_prefix}/jobs/{job_id}/output.pdf")
        assert response.status_code == 409  # Conflict - not done


class TestJobEventsSSE:
    """Tests for SSE events endpoint."""

    @pytest.mark.skip(reason="SSE streaming tests hang in TestClient - requires integration test")
    def test_events_endpoint_exists(
        self,
        client: TestClient,
        api_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test that events endpoint returns streaming response.

        Note: This test is skipped because SSE streaming endpoints hang in TestClient.
        The SSE functionality should be tested in integration tests instead.
        """
        pass

    def test_events_job_not_found(self, client: TestClient, api_prefix: str) -> None:
        """Test events endpoint for non-existent job."""
        response = client.get(f"{api_prefix}/jobs/non-existent-id/events")
        assert response.status_code == 404
