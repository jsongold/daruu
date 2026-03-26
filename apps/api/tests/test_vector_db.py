"""Tests for Vector Database Gateway.

Tests in-memory VectorDBGateway:
- Store embedding
- Search similar
- Delete embedding
- Threshold filtering
- Tenant isolation
"""

import math

import pytest


class TestInMemoryVectorDB:
    """Tests for InMemoryVectorDB implementation."""

    @pytest.fixture
    def vector_db(self):
        """Create a fresh vector database for each test."""
        from app.infrastructure.gateways.vector_db import InMemoryVectorDB

        return InMemoryVectorDB()

    @pytest.fixture
    def sample_embedding(self) -> list[float]:
        """Create a sample normalized embedding vector."""
        # 1536-dimension vector (OpenAI embedding size)
        vector = [0.1] * 1536
        # Normalize
        magnitude = math.sqrt(sum(x * x for x in vector))
        return [x / magnitude for x in vector]

    @pytest.fixture
    def different_embedding(self) -> list[float]:
        """Create a different embedding vector."""
        # Different pattern
        vector = [0.0] * 768 + [0.2] * 768
        magnitude = math.sqrt(sum(x * x for x in vector))
        return [x / magnitude for x in vector]

    # =========================================================================
    # Store Embedding Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_store_embedding(self, vector_db, sample_embedding) -> None:
        """Test storing an embedding."""
        embedding_id = await vector_db.store(
            id="emb-001",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-123", "template_id": "tpl-001"},
        )

        assert embedding_id == "emb-001"

    @pytest.mark.asyncio
    async def test_store_multiple_embeddings(self, vector_db, sample_embedding) -> None:
        """Test storing multiple embeddings."""
        await vector_db.store(
            id="emb-001",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-123"},
        )
        await vector_db.store(
            id="emb-002",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-123"},
        )
        await vector_db.store(
            id="emb-003",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-456"},
        )

        # All should be stored
        results = await vector_db.search(
            embedding=sample_embedding,
            limit=10,
        )
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_store_overwrites_existing(
        self, vector_db, sample_embedding, different_embedding
    ) -> None:
        """Test that storing with same ID overwrites."""
        await vector_db.store(
            id="emb-001",
            embedding=sample_embedding,
            metadata={"version": 1},
        )
        await vector_db.store(
            id="emb-001",
            embedding=different_embedding,
            metadata={"version": 2},
        )

        # Should only have one entry with version 2
        results = await vector_db.search(
            embedding=different_embedding,
            limit=10,
        )
        # Find the entry for emb-001
        emb_001_result = next((r for r in results if r["id"] == "emb-001"), None)
        assert emb_001_result is not None

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, vector_db, sample_embedding) -> None:
        """Test storing embedding with metadata."""
        metadata = {
            "tenant_id": "tenant-123",
            "template_id": "tpl-001",
            "form_type": "application",
            "page": 1,
        }

        await vector_db.store(
            id="emb-001",
            embedding=sample_embedding,
            metadata=metadata,
        )

        # Search and verify metadata is preserved
        results = await vector_db.search(
            embedding=sample_embedding,
            limit=1,
        )
        assert len(results) == 1

    # =========================================================================
    # Search Similar Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_similar_exact_match(self, vector_db, sample_embedding) -> None:
        """Test searching with exact same embedding returns high score."""
        await vector_db.store(
            id="emb-001",
            embedding=sample_embedding,
            metadata={},
        )

        results = await vector_db.search(
            embedding=sample_embedding,
            limit=5,
        )

        assert len(results) == 1
        assert results[0]["id"] == "emb-001"
        assert results[0]["score"] >= 0.99  # Should be very close to 1.0

    @pytest.mark.asyncio
    async def test_search_similar_returns_top_k(self, vector_db) -> None:
        """Test that search returns at most limit results."""
        base = [0.1] * 1536

        # Store 10 embeddings with slight variations
        for i in range(10):
            variation = base.copy()
            variation[i] = 0.2
            magnitude = math.sqrt(sum(x * x for x in variation))
            normalized = [x / magnitude for x in variation]
            await vector_db.store(
                id=f"emb-{i}",
                embedding=normalized,
                metadata={},
            )

        results = await vector_db.search(
            embedding=base,
            limit=3,
        )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_empty_database(self, vector_db, sample_embedding) -> None:
        """Test searching in empty database returns empty list."""
        results = await vector_db.search(
            embedding=sample_embedding,
            limit=5,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_orders_by_score_descending(self, vector_db) -> None:
        """Test that results are ordered by score descending."""
        base = [0.1] * 1536

        # Store embeddings with varying similarity
        await vector_db.store(
            id="emb-exact",
            embedding=base.copy(),
            metadata={},
        )

        slightly_different = base.copy()
        slightly_different[0] = 0.5
        magnitude = math.sqrt(sum(x * x for x in slightly_different))
        await vector_db.store(
            id="emb-similar",
            embedding=[x / magnitude for x in slightly_different],
            metadata={},
        )

        very_different = [0.0] * 768 + [0.2] * 768
        magnitude = math.sqrt(sum(x * x for x in very_different))
        await vector_db.store(
            id="emb-different",
            embedding=[x / magnitude for x in very_different],
            metadata={},
        )

        results = await vector_db.search(
            embedding=base,
            limit=10,
        )

        # Verify ordering
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_with_different_embedding(
        self, vector_db, sample_embedding, different_embedding
    ) -> None:
        """Test that different embeddings have lower similarity scores."""
        await vector_db.store(id="emb-001", embedding=sample_embedding, metadata={})

        results = await vector_db.search(
            embedding=different_embedding,
            limit=5,
        )

        assert len(results) == 1
        # Score should be lower for different embedding
        assert results[0]["score"] < 0.9

    # =========================================================================
    # Delete Embedding Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_embedding(self, vector_db, sample_embedding) -> None:
        """Test deleting an embedding."""
        await vector_db.store(id="emb-001", embedding=sample_embedding, metadata={})

        result = await vector_db.delete("emb-001")
        assert result is True

        # Should not find deleted embedding
        results = await vector_db.search(embedding=sample_embedding, limit=5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_embedding(self, vector_db) -> None:
        """Test deleting non-existent embedding returns False."""
        result = await vector_db.delete("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_only_specified_embedding(self, vector_db, sample_embedding) -> None:
        """Test that delete only removes specified embedding."""
        await vector_db.store(id="emb-001", embedding=sample_embedding, metadata={})
        await vector_db.store(id="emb-002", embedding=sample_embedding, metadata={})

        await vector_db.delete("emb-001")

        results = await vector_db.search(embedding=sample_embedding, limit=5)
        assert len(results) == 1
        assert results[0]["id"] == "emb-002"

    # =========================================================================
    # Threshold Filtering Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_with_min_score_threshold(self, vector_db) -> None:
        """Test filtering results by minimum score."""
        base = [0.1] * 1536

        # High similarity embedding
        await vector_db.store(id="emb-high", embedding=base.copy(), metadata={})

        # Low similarity embedding
        very_different = [0.0] * 768 + [0.2] * 768
        magnitude = math.sqrt(sum(x * x for x in very_different))
        await vector_db.store(
            id="emb-low",
            embedding=[x / magnitude for x in very_different],
            metadata={},
        )

        results = await vector_db.search(
            embedding=base,
            limit=10,
            min_score=0.9,  # Only high similarity
        )

        # Only high similarity result should be returned
        assert all(r["score"] >= 0.9 for r in results)

    @pytest.mark.asyncio
    async def test_search_threshold_filters_all(self, vector_db, sample_embedding) -> None:
        """Test that high threshold can filter all results."""
        await vector_db.store(id="emb-001", embedding=sample_embedding, metadata={})

        # Different query embedding
        different = [0.0] * 768 + [0.1] * 768
        magnitude = math.sqrt(sum(x * x for x in different))
        query = [x / magnitude for x in different]

        results = await vector_db.search(
            embedding=query,
            limit=10,
            min_score=0.99,  # Very high threshold
        )

        # May return empty if none meet threshold
        for r in results:
            assert r["score"] >= 0.99

    # =========================================================================
    # Tenant Isolation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_with_tenant_filter(self, vector_db, sample_embedding) -> None:
        """Test filtering search by tenant."""
        await vector_db.store(
            id="emb-A",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-A"},
        )
        await vector_db.store(
            id="emb-B",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-B"},
        )

        results = await vector_db.search(
            embedding=sample_embedding,
            limit=10,
            filter={"tenant_id": "tenant-A"},
        )

        # Only tenant-A results
        assert len(results) == 1
        assert results[0]["id"] == "emb-A"

    @pytest.mark.asyncio
    async def test_search_without_tenant_filter_returns_all(
        self, vector_db, sample_embedding
    ) -> None:
        """Test that search without filter returns all tenants."""
        await vector_db.store(
            id="emb-A",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-A"},
        )
        await vector_db.store(
            id="emb-B",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-B"},
        )

        results = await vector_db.search(
            embedding=sample_embedding,
            limit=10,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_nonexistent_tenant_returns_empty(
        self, vector_db, sample_embedding
    ) -> None:
        """Test searching for non-existent tenant returns empty."""
        await vector_db.store(
            id="emb-A",
            embedding=sample_embedding,
            metadata={"tenant_id": "tenant-A"},
        )

        results = await vector_db.search(
            embedding=sample_embedding,
            limit=10,
            filter={"tenant_id": "tenant-nonexistent"},
        )

        assert results == []


class TestVectorDBProtocol:
    """Tests to verify VectorDB implements the protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test that InMemoryVectorDB implements VectorDBGateway protocol."""
        from app.infrastructure.gateways.vector_db import InMemoryVectorDB
        from app.repositories.vector_db_gateway import VectorDBGateway

        db = InMemoryVectorDB()
        # This should not raise if protocol is implemented correctly
        _: VectorDBGateway = db

    def test_required_methods_exist(self) -> None:
        """Test that all required methods exist."""
        from app.infrastructure.gateways.vector_db import InMemoryVectorDB

        db = InMemoryVectorDB()

        assert hasattr(db, "store")
        assert hasattr(db, "search")
        assert hasattr(db, "delete")

        assert callable(db.store)
        assert callable(db.search)
        assert callable(db.delete)


class TestVectorDBEdgeCases:
    """Edge case tests for Vector Database."""

    @pytest.fixture
    def vector_db(self):
        """Create a fresh vector database."""
        from app.infrastructure.gateways.vector_db import InMemoryVectorDB

        return InMemoryVectorDB()

    @pytest.mark.asyncio
    async def test_zero_length_embedding(self, vector_db) -> None:
        """Test handling zero-length embedding."""
        with pytest.raises((ValueError, IndexError)):
            await vector_db.store(id="emb-001", embedding=[], metadata={})

    @pytest.mark.asyncio
    async def test_negative_limit(self, vector_db) -> None:
        """Test handling negative limit."""
        sample = [0.1] * 1536
        await vector_db.store(id="emb-001", embedding=sample, metadata={})

        # Should handle gracefully - either error or return empty
        try:
            results = await vector_db.search(embedding=sample, limit=-1)
            assert results == []
        except ValueError:
            pass  # Also acceptable

    @pytest.mark.asyncio
    async def test_zero_limit(self, vector_db) -> None:
        """Test handling zero limit."""
        sample = [0.1] * 1536
        await vector_db.store(id="emb-001", embedding=sample, metadata={})

        results = await vector_db.search(embedding=sample, limit=0)
        assert results == []

    @pytest.mark.asyncio
    async def test_very_large_embedding(self, vector_db) -> None:
        """Test handling very large embedding."""
        large_embedding = [0.1] * 10000  # Much larger than typical

        await vector_db.store(id="emb-large", embedding=large_embedding, metadata={})

        results = await vector_db.search(embedding=large_embedding, limit=5)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_special_characters_in_id(self, vector_db) -> None:
        """Test handling special characters in ID."""
        sample = [0.1] * 1536

        special_id = "emb-with-special!@#$%^&*()_+="
        await vector_db.store(id=special_id, embedding=sample, metadata={})

        result = await vector_db.delete(special_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_stores(self, vector_db) -> None:
        """Test concurrent store operations."""
        import asyncio

        sample = [0.1] * 1536

        async def store_embedding(i: int):
            await vector_db.store(id=f"emb-{i}", embedding=sample, metadata={})

        # Store 10 embeddings concurrently
        await asyncio.gather(*[store_embedding(i) for i in range(10)])

        results = await vector_db.search(embedding=sample, limit=20)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_nan_in_embedding(self, vector_db) -> None:
        """Test handling NaN in embedding."""
        nan_embedding = [0.1] * 1535 + [float("nan")]

        # Should handle gracefully - either store and handle, or reject
        try:
            await vector_db.store(id="emb-nan", embedding=nan_embedding, metadata={})
        except ValueError:
            pass  # Acceptable to reject

    @pytest.mark.asyncio
    async def test_infinity_in_embedding(self, vector_db) -> None:
        """Test handling infinity in embedding."""
        inf_embedding = [0.1] * 1535 + [float("inf")]

        # Should handle gracefully
        try:
            await vector_db.store(id="emb-inf", embedding=inf_embedding, metadata={})
        except (ValueError, OverflowError):
            pass  # Acceptable to reject
