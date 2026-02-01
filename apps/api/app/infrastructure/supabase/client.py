"""Supabase client setup.

Provides the Supabase client instance for database, auth, and storage operations.
"""

from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.config import get_settings


@runtime_checkable
class SupabaseClient(Protocol):
    """Protocol for Supabase client.

    This protocol defines the expected interface for Supabase operations.
    The actual implementation uses the supabase-py library.
    """

    @property
    def auth(self) -> "AuthClient":
        """Get the auth client."""
        ...

    @property
    def storage(self) -> "StorageClient":
        """Get the storage client."""
        ...

    def table(self, table_name: str) -> "TableClient":
        """Get a table client for database operations."""
        ...


class AuthClient(Protocol):
    """Protocol for Supabase Auth client."""

    async def sign_in_with_password(
        self, email: str, password: str
    ) -> dict:
        """Sign in with email and password."""
        ...

    async def sign_up(self, email: str, password: str) -> dict:
        """Sign up a new user."""
        ...

    async def sign_out(self) -> None:
        """Sign out the current user."""
        ...

    async def get_user(self, jwt: str) -> dict | None:
        """Get user from JWT token."""
        ...


class StorageClient(Protocol):
    """Protocol for Supabase Storage client."""

    def from_(self, bucket_name: str) -> "BucketClient":
        """Get a bucket client."""
        ...


class BucketClient(Protocol):
    """Protocol for Supabase bucket operations."""

    async def upload(
        self,
        path: str,
        file: bytes,
        file_options: dict | None = None,
    ) -> dict:
        """Upload a file to the bucket."""
        ...

    async def download(self, path: str) -> bytes:
        """Download a file from the bucket."""
        ...

    async def remove(self, paths: list[str]) -> dict:
        """Remove files from the bucket."""
        ...

    async def list(self, path: str = "") -> list[dict]:
        """List files in the bucket."""
        ...

    def get_public_url(self, path: str) -> str:
        """Get the public URL for a file."""
        ...

    async def create_signed_url(
        self, path: str, expires_in: int
    ) -> dict:
        """Create a signed URL for private file access."""
        ...


class TableClient(Protocol):
    """Protocol for Supabase table operations."""

    def select(self, columns: str = "*") -> "QueryBuilder":
        """Start a select query."""
        ...

    def insert(self, data: dict | list[dict]) -> "QueryBuilder":
        """Start an insert query."""
        ...

    def update(self, data: dict) -> "QueryBuilder":
        """Start an update query."""
        ...

    def delete(self) -> "QueryBuilder":
        """Start a delete query."""
        ...


class QueryBuilder(Protocol):
    """Protocol for Supabase query building."""

    def eq(self, column: str, value: str | int | bool) -> "QueryBuilder":
        """Filter by equality."""
        ...

    def neq(self, column: str, value: str | int | bool) -> "QueryBuilder":
        """Filter by inequality."""
        ...

    def limit(self, count: int) -> "QueryBuilder":
        """Limit results."""
        ...

    def order(
        self, column: str, desc: bool = False
    ) -> "QueryBuilder":
        """Order results."""
        ...

    async def execute(self) -> dict:
        """Execute the query."""
        ...


class MockSupabaseClient:
    """Mock Supabase client for development/testing when Supabase is not configured."""

    def __init__(self) -> None:
        self._auth = MockAuthClient()
        self._storage = MockStorageClient()

    @property
    def auth(self) -> "MockAuthClient":
        return self._auth

    @property
    def storage(self) -> "MockStorageClient":
        return self._storage

    def table(self, table_name: str) -> "MockTableClient":
        return MockTableClient(table_name)


class MockAuthClient:
    """Mock Auth client."""

    async def sign_in_with_password(
        self, email: str, password: str
    ) -> dict:
        raise NotImplementedError("Supabase Auth not configured")

    async def sign_up(self, email: str, password: str) -> dict:
        raise NotImplementedError("Supabase Auth not configured")

    async def sign_out(self) -> None:
        raise NotImplementedError("Supabase Auth not configured")

    async def get_user(self, jwt: str) -> dict | None:
        raise NotImplementedError("Supabase Auth not configured")


class MockStorageClient:
    """Mock Storage client."""

    def from_(self, bucket_name: str) -> "MockBucketClient":
        return MockBucketClient(bucket_name)


class MockBucketClient:
    """Mock Bucket client."""

    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name

    async def upload(
        self,
        path: str,
        file: bytes,
        file_options: dict | None = None,
    ) -> dict:
        raise NotImplementedError("Supabase Storage not configured")

    async def download(self, path: str) -> bytes:
        raise NotImplementedError("Supabase Storage not configured")

    async def remove(self, paths: list[str]) -> dict:
        raise NotImplementedError("Supabase Storage not configured")

    async def list(self, path: str = "") -> list[dict]:
        raise NotImplementedError("Supabase Storage not configured")

    def get_public_url(self, path: str) -> str:
        raise NotImplementedError("Supabase Storage not configured")

    async def create_signed_url(
        self, path: str, expires_in: int
    ) -> dict:
        raise NotImplementedError("Supabase Storage not configured")


class MockTableClient:
    """Mock Table client."""

    def __init__(self, table_name: str) -> None:
        self._table_name = table_name

    def select(self, columns: str = "*") -> "MockQueryBuilder":
        return MockQueryBuilder()

    def insert(self, data: dict | list[dict]) -> "MockQueryBuilder":
        return MockQueryBuilder()

    def update(self, data: dict) -> "MockQueryBuilder":
        return MockQueryBuilder()

    def delete(self) -> "MockQueryBuilder":
        return MockQueryBuilder()


class MockQueryBuilder:
    """Mock Query builder."""

    def eq(self, column: str, value: str | int | bool) -> "MockQueryBuilder":
        return self

    def neq(self, column: str, value: str | int | bool) -> "MockQueryBuilder":
        return self

    def limit(self, count: int) -> "MockQueryBuilder":
        return self

    def order(
        self, column: str, desc: bool = False
    ) -> "MockQueryBuilder":
        return self

    async def execute(self) -> dict:
        raise NotImplementedError("Supabase Database not configured")


@lru_cache
def get_supabase_client() -> SupabaseClient | MockSupabaseClient:
    """Get the Supabase client instance.

    Returns a real Supabase client if configured, otherwise returns
    a mock client that raises NotImplementedError for all operations.
    """
    settings = get_settings()

    # Check if Supabase is configured
    # Backend uses secret key (bypasses RLS)
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_secret_key

    if not supabase_url or not supabase_key:
        # Return mock client when Supabase is not configured
        return MockSupabaseClient()

    # Import and create real client only when configured
    try:
        from supabase import create_client, Client

        client: Client = create_client(supabase_url, supabase_key)
        return client  # type: ignore[return-value]
    except ImportError:
        # supabase package not installed
        return MockSupabaseClient()
