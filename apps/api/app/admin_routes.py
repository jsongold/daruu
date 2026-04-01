"""Admin API routes for table browsing and comparison."""

from fastapi import APIRouter, HTTPException, Query

from app.admin_service import AdminService

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
_svc = AdminService()


@admin_router.get("/tables")
async def list_tables():
    return _svc.list_tables()


@admin_router.get("/tables/{table_name}/records")
async def list_records(
    table_name: str,
    search: str = Query("", description="Search text"),
    sort_by: str = Query("created_at", description="Sort column"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        return _svc.list_records(
            table_name, search or None, sort_by, sort_order, limit, offset
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@admin_router.get("/tables/{table_name}/records/{record_id}")
async def get_record(table_name: str, record_id: str):
    try:
        record = _svc.get_record(table_name, record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
