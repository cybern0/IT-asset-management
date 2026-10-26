# Fiches de detention (liste croisee, PDF, signature) et image du materiel
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.database import get_db
from crud_api.core.errors import ConflictError, NotFoundError, UnprocessableError
from crud_api.schemas.fiche import AttributionCreate, AttributionOut, MotifIn, RemiseIn, SelectionIn, ValidationIn
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


@router.get("/attributions/{fiche_id}", response_model=AttributionOut, tags=TAG)
async def get_attribution(fiche_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_detention(db, fiche_id)


@router.get("/affectations/{affectation_id}/attribution", response_model=AttributionOut, tags=TAG)
async def attribution_of_affectation(affectation_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_by_affectation(db, affectation_id)


@router.post("/attributions/{fiche_id}/valider", response_model=AttributionOut, tags=TAG)
async def validate_request(fiche_id: int, data: ValidationIn, db: AsyncSession = Depends(get_db)):
    """Etape 1 : validation par le manager."""
    return await fiche_service.validate(db, fiche_id, data.valide_par, data.date_validation)


@router.post("/attributions/{fiche_id}/refuser", response_model=AttributionOut, tags=TAG)
async def refuse_request(fiche_id: int, data: MotifIn, db: AsyncSession = Depends(get_db)):
    return await fiche_service.refuse(db, fiche_id, data.motif)


@router.post("/attributions/{fiche_id}/annuler", response_model=AttributionOut, tags=TAG)
async def cancel_attribution(fiche_id: int, data: MotifIn, db: AsyncSession = Depends(get_db)):
    return await fiche_service.cancel(db, fiche_id, data.motif)


@router.post("/attributions/{fiche_id}/selectionner", response_model=AttributionOut, tags=TAG)
async def select_equipment(fiche_id: int, data: SelectionIn, db: AsyncSession = Depends(get_db)):
    """Etapes 2 et 3 : choix de l'equipement en stock ; la fiche est generee automatiquement."""
    return await fiche_service.select_equipment(db, fiche_id, data.materiel_id)


@router.post("/attributions/{fiche_id}/signer", response_model=AttributionOut, tags=TAG)
async def sign_fiche(
    fiche_id: int,
    mode_signature: str = Form(...),
    date_signature: str | None = Form(None),
    signe_par: str | None = Form(None),
    fichier: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Etape 4 : signature (date du jour par defaut) ; scan du document signe facultatif."""
    signed_on = None
    if date_signature and date_signature.strip():
        try:
            signed_on = date.fromisoformat(date_signature.strip())
        except ValueError as exc:
            raise UnprocessableError("Date invalide (AAAA-MM-JJ).", field="date_signature") from exc
    return await fiche_service.sign(
        db, fiche_id, signed_on, mode_signature.strip().upper(), (signe_par or "").strip() or None,
        fichier if fichier and fichier.filename else None,
    )


@router.post("/attributions/{fiche_id}/annuler-signature", response_model=AttributionOut, tags=TAG)
async def unsign_fiche(fiche_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.unsign(db, fiche_id)


@router.post("/attributions/{fiche_id}/remettre", response_model=AttributionOut, tags=TAG)
async def hand_over(fiche_id: int, data: RemiseIn, db: AsyncSession = Depends(get_db)):
    """Etapes 5 et 6 : remise physique, puis le materiel passe a « Attribue » (affectation creee)."""
    return await fiche_service.hand_over(db, fiche_id, data)


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


@router.get("/attributions/{fiche_id}/fichier-signe", tags=TAG)
async def signed_scan(fiche_id: int, db: AsyncSession = Depends(get_db)):
    rel = await fiche_service.scan_path(db, fiche_id)
    return FileResponse(file_store.path_of(rel), media_type=file_store.media_type(rel))


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
