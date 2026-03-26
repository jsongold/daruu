"""Repository interface for annotation pairs."""

from typing import Protocol

from app.models.annotation import AnnotationPairCreate, AnnotationPairModel


class AnnotationPairRepository(Protocol):
    """Port for annotation pair persistence."""

    def create(self, document_id: str, data: AnnotationPairCreate) -> AnnotationPairModel: ...

    def list_by_document(self, document_id: str) -> list[AnnotationPairModel]: ...

    def delete(self, pair_id: str) -> bool: ...

    def delete_by_document(self, document_id: str) -> int: ...
