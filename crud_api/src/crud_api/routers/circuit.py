# Circuit de demande et notifications (RBAC par permissions, voir parc_10.sql)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.core.deps import Principal, requires
from crud_api.schemas.circuit import ApprouverIn, DemandeCreate, DemandeOut, NotificationOut
from crud_api.schemas.fiche import AvancerIn, MotifIn
from crud_api.services import circuit_service as svc

router = APIRouter(tags=["Demandes"])
_voir = requires("demande.voir_propres", "demande.voir_service", "demande.voir_toutes")


@router.get("/demandes/options")
async def options(p: Principal = Depends(requires("demande.creer", "demande.approuver")), db: AsyncSession = Depends(get_db)):
    return await svc.options(db, p)


@router.get("/demandes", response_model=list[DemandeOut])
async def list_demandes(p: Principal = Depends(_voir), db: AsyncSession = Depends(get_db)):
    return await svc.list_demandes(db, p)


@router.post("/demandes", response_model=DemandeOut, status_code=201)
async def create(data: DemandeCreate, p: Principal = Depends(requires("demande.creer")), db: AsyncSession = Depends(get_db)):
    return await svc.create(db, p, data)


@router.get("/demandes/{fiche_id}", response_model=DemandeOut)
async def get_one(fiche_id: int, p: Principal = Depends(_voir), db: AsyncSession = Depends(get_db)):
    return await svc.get_demande(db, p, fiche_id)


@router.post("/demandes/{fiche_id}/approuver", response_model=DemandeOut)
async def approve(fiche_id: int, data: ApprouverIn, p: Principal = Depends(requires("demande.approuver")), db: AsyncSession = Depends(get_db)):
    return await svc.approve(db, p, fiche_id, data)


@router.post("/demandes/{fiche_id}/refuser", response_model=DemandeOut)
async def refuse(fiche_id: int, data: MotifIn, p: Principal = Depends(requires("demande.approuver")), db: AsyncSession = Depends(get_db)):
    return await svc.refuse(db, p, fiche_id, data.motif)


@router.post("/demandes/{fiche_id}/signer-agent", response_model=DemandeOut)
async def sign_agent(fiche_id: int, p: Principal = Depends(requires("fiche.signer_agent")), db: AsyncSession = Depends(get_db)):
    return await svc.sign_agent(db, p, fiche_id)


@router.post("/demandes/{fiche_id}/signer-chef", response_model=DemandeOut)
async def sign_chef(fiche_id: int, p: Principal = Depends(requires("fiche.signer_chef")), db: AsyncSession = Depends(get_db)):
    return await svc.sign_chef(db, p, fiche_id)


@router.post("/demandes/{fiche_id}/remettre", response_model=DemandeOut)
async def hand_over(fiche_id: int, data: AvancerIn, p: Principal = Depends(requires("fiche.remettre")), db: AsyncSession = Depends(get_db)):
    return await svc.hand_over(db, p, fiche_id, data)


@router.post("/demandes/{fiche_id}/approuver-reception", response_model=DemandeOut)
async def approve_reception(fiche_id: int, p: Principal = Depends(requires("reception.approuver")), db: AsyncSession = Depends(get_db)):
    return await svc.approve_reception(db, p, fiche_id)


@router.get("/demandes/{fiche_id}/notifications", response_model=list[NotificationOut])
async def fiche_notifications(fiche_id: int, p: Principal = Depends(_voir), db: AsyncSession = Depends(get_db)):
    """Liens mailto: / sms: / wa.me a ouvrir pour prevenir la personne suivante (aucun serveur d'envoi)."""
    return await svc.fiche_notifications(db, p, fiche_id)


@router.get("/notifications/mes", response_model=list[NotificationOut])
async def my_notifications(p: Principal = Depends(requires("demande.voir_propres", "demande.voir_service", "demande.voir_toutes")), db: AsyncSession = Depends(get_db)):
    return await svc.my_notifications(db, p)


@router.post("/notifications/{notif_id}/envoyee", status_code=204)
async def sent(notif_id: int, p: Principal = Depends(requires("demande.creer", "demande.voir_service", "demande.voir_toutes", "fiche.signer_chef")), db: AsyncSession = Depends(get_db)):
    await svc.mark(db, p, notif_id, "ENVOYEE")


@router.post("/notifications/{notif_id}/lue", status_code=204)
async def read(notif_id: int, p: Principal = Depends(requires("demande.voir_propres", "demande.voir_service", "demande.voir_toutes")), db: AsyncSession = Depends(get_db)):
    await svc.mark(db, p, notif_id, "LUE")
