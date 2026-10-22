# Journal d'audit : lecture seule (les lignes sont ecrites par les services)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.schemas.audit import AuditOut
from crud_api.services import audit_service

router = APIRouter()


@router.get("", response_model=list[AuditOut])
async def list_audit(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    return await audit_service.list_entries(db, limit=limit, offset=offset)
