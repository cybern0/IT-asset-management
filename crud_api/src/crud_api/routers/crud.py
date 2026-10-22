# Fabrique de routes CRUD : GET liste, GET un, POST, PATCH, DELETE
# (pas de `from __future__ import annotations` ici : FastAPI lit les annotations locales)
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.services.base import CRUDService


def crud_router(
    *,
    service: CRUDService,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    out_schema: type[BaseModel],
    immutable: bool = False,
) -> APIRouter:
    """`immutable=True` : creation et lecture seulement (ex. mouvements de stock)."""
    router = APIRouter()

    @router.get("", response_model=list[out_schema])
    async def list_items(
        db: AsyncSession = Depends(get_db),
        limit: int = Query(1000, ge=1, le=5000),
        offset: int = Query(0, ge=0),
    ):
        return await service.list(db, limit=limit, offset=offset)

    @router.get("/{item_id}", response_model=out_schema)
    async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
        return await service.get(db, item_id)

    @router.post("", response_model=out_schema, status_code=201)
    async def create_item(data: create_schema, db: AsyncSession = Depends(get_db)):
        return await service.create(db, data)

    if not immutable:

        @router.patch("/{item_id}", response_model=out_schema)
        async def update_item(item_id: int, data: update_schema, db: AsyncSession = Depends(get_db)):
            return await service.update(db, item_id, data)

        @router.delete("/{item_id}", status_code=204)
        async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
            await service.delete(db, item_id)
            return Response(status_code=204)

    return router
