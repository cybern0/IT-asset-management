# Dossiers d'attribution (fiches de detention : etapes, PDF) et image du materiel
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.database import get_db
from crud_api.core.deps import require_admin
from crud_api.core.errors import ConflictError, NotFoundError
from crud_api.schemas.fiche import AttributionCreate, AttributionDirecteIn, AttributionOut, AvancerIn, MotifIn, SignatureIn
from crud_api.schemas.materiel import MaterielOut
from crud_api.services import audit_service, fiche_pdf, fiche_service, file_store
from crud_api.services.materiel_service import materiel_service

router = APIRouter()


# ----------------------------- dossiers d'attribution (fiches de detention) -----------------------------
TAG = ["Attributions"]


@router.get("/attributions", response_model=list[AttributionOut], tags=TAG)
async def list_attributions(db: AsyncSession = Depends(get_db), limit: int = Query(5000, ge=1, le=5000)):
    return await fiche_service.list_detentions(db, limit=limit)


@router.post("/attributions", response_model=AttributionOut, status_code=201, tags=TAG)
async def create_attribution(data: AttributionCreate, db: AsyncSession = Depends(get_db)):
    """Etape 1 : demande d'equipement (valide_par renseigne si le manager a deja valide)."""
    return await fiche_service.create_request(db, data)


@router.post("/attributions/directe", response_model=AttributionOut, status_code=201, tags=TAG)
async def create_attribution_directe(data: AttributionDirecteIn, db: AsyncSession = Depends(get_db)):
    """Attribution en une saisie : demande, equipement, fiche, signature et remise enregistrees ensemble."""
    return await fiche_service.create_direct(db, data)


@router.get("/attributions/{fiche_id}", response_model=AttributionOut, tags=TAG)
async def get_attribution(fiche_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_detention(db, fiche_id)


@router.get("/affectations/{affectation_id}/attribution", response_model=AttributionOut, tags=TAG)
async def attribution_of_affectation(affectation_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_by_affectation(db, affectation_id)


@router.post("/attributions/{fiche_id}/avancer", response_model=AttributionOut, tags=TAG)
async def advance_attribution(fiche_id: int, data: AvancerIn, db: AsyncSession = Depends(get_db)):
    """L'etape en cours est faite (validation du manager, equipement choisi, signature ou remise) : etape suivante.
    A la remise, l'affectation est creee et le materiel passe a « Attribue »."""
    return await fiche_service.advance(db, fiche_id, data)


@router.post("/attributions/{fiche_id}/signature", response_model=AttributionOut, tags=TAG)
async def set_attribution_signature(
    fiche_id: int, data: SignatureIn, db: AsyncSession = Depends(get_db), _admin=Depends(require_admin)
):
    """L'administrateur fixe a la main l'etat de signature de la fiche : « signee » ou « a signer »."""
    return await fiche_service.set_signature(db, fiche_id, data)


@router.post("/attributions/{fiche_id}/reculer", response_model=AttributionOut, tags=TAG)
async def back_attribution(fiche_id: int, db: AsyncSession = Depends(get_db)):
    """Defait la derniere etape faite."""
    return await fiche_service.back(db, fiche_id)


@router.post("/attributions/{fiche_id}/clore", response_model=AttributionOut, tags=TAG)
async def close_attribution(fiche_id: int, data: MotifIn, db: AsyncSession = Depends(get_db)):
    """Refuse la demande (avant validation) ou annule le dossier (apres)."""
    return await fiche_service.close(db, fiche_id, data.motif)


@router.get("/attributions/{fiche_id}/pdf", tags=TAG)
async def fiche_pdf_file(fiche_id: int, db: AsyncSession = Depends(get_db)):
    d = await fiche_service.get_detention(db, fiche_id)
    if d["materiel_id"] is None:
        raise ConflictError("Sélectionnez d’abord un équipement : la fiche n’est pas encore générée.")
    pdf = fiche_pdf.build_pdf(d, get_settings().structure_name, await fiche_service.category_types(db))
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{d["reference"]}.pdf"'},
    )


# ----------------------------- image du materiel -----------------------------
@router.get("/materiels/{materiel_id}/image", tags=["Matériel"])
async def get_image(materiel_id: int, db: AsyncSession = Depends(get_db)):
    m = await materiel_service.get(db, materiel_id)
    if not m.image_chemin:
        raise NotFoundError("Ce matériel n’a pas d’image.")
    return FileResponse(file_store.path_of(m.image_chemin), media_type=file_store.media_type(m.image_chemin))


@router.post("/materiels/{materiel_id}/image", response_model=MaterielOut, tags=["Matériel"])
async def put_image(materiel_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Ajoute ou remplace l'image (JPEG, PNG ou WebP, 5 Mo maximum)."""
    m = await materiel_service.get(db, materiel_id)
    old = m.image_chemin
    m.image_chemin = await file_store.save(
        file, "materiels", str(m.id), file_store.IMAGE_TYPES, get_settings().max_image_mb
    )
    await audit_service.record(db, "IMAGE_SET", "materiel", m.id, None)
    await db.commit()
    file_store.remove(old)
    return await materiel_service.get(db, materiel_id)


@router.delete("/materiels/{materiel_id}/image", status_code=204, tags=["Matériel"])
async def delete_image(materiel_id: int, db: AsyncSession = Depends(get_db)):
    m = await materiel_service.get(db, materiel_id)
    old = m.image_chemin
    m.image_chemin = None
    await audit_service.record(db, "IMAGE_DELETE", "materiel", m.id, None)
    await db.commit()
    file_store.remove(old)
    return Response(status_code=204)
