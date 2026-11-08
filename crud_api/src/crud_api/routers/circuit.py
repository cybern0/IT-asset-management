# Affectation directe (transfert) et options des formulaires du circuit (RBAC par permissions, voir parc_10.sql)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.core.deps import Principal, requires
from crud_api.schemas.circuit import TransfertCreate
from crud_api.schemas.materiel import AffectationOut
from crud_api.services import circuit_service as svc

router = APIRouter(tags=["Circuit"])


@router.get("/circuit/options")
async def options(p: Principal = Depends(requires("demande.creer", "demande.approuver")), db: AsyncSession = Depends(get_db)):
    """Categories, materiels en stock (nouvelle attribution) et materiels detenus (nouvelle affectation)."""
    return await svc.options(db, p)


@router.post("/transferts", response_model=AffectationOut, status_code=201, tags=["Affectations"])
async def transfer(data: TransfertCreate, p: Principal = Depends(requires("affectation.transferer")), db: AsyncSession = Depends(get_db)):
    """Affectation directe : retire un materiel a son detenteur et le donne a un autre agent (depositaire comptable)."""
    return await svc.transfer(db, p, data)
