# Tracabilite des materiels : lecture seule (le parcours est reconstitue, jamais saisi)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.services import tracabilite_service

router = APIRouter()


@router.get("")
async def list_materiels(db: AsyncSession = Depends(get_db)):
    """Une ligne par materiel : detenteur actuel, nombre de detenteurs successifs, dernier mouvement."""
    return await tracabilite_service.summary(db)


@router.get("/{materiel_id}")
async def get_parcours(materiel_id: int, db: AsyncSession = Depends(get_db)):
    """Parcours chronologique d'un materiel."""
    return await tracabilite_service.detail(db, materiel_id)
