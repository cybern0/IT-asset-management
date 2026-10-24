# Fiches de detention (liste croisee, PDF, signature) et image du materiel
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.database import get_db
from crud_api.core.errors import NotFoundError, UnprocessableError
from crud_api.schemas.fiche import DetentionOut
from crud_api.schemas.materiel import MaterielOut
from crud_api.services import audit_service, fiche_pdf, fiche_service, file_store
from crud_api.services.materiel_service import materiel_service

router = APIRouter()


# ----------------------------- fiches de detention -----------------------------
@router.get("/fiches-detention", response_model=list[DetentionOut], tags=["Fiches de détention"])
async def list_fiches(db: AsyncSession = Depends(get_db), limit: int = Query(5000, ge=1, le=5000)):
    return await fiche_service.list_detentions(db, limit=limit)


@router.get("/fiches-detention/{fiche_id}", response_model=DetentionOut, tags=["Fiches de détention"])
async def get_fiche(fiche_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_detention(db, fiche_id)


@router.get("/affectations/{affectation_id}/fiche", response_model=DetentionOut, tags=["Fiches de détention"])
async def fiche_of_affectation(affectation_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.get_by_affectation(db, affectation_id)


@router.get("/fiches-detention/{fiche_id}/pdf", tags=["Fiches de détention"])
async def fiche_pdf_file(fiche_id: int, db: AsyncSession = Depends(get_db)):
    d = await fiche_service.get_detention(db, fiche_id)
    pdf = fiche_pdf.build_pdf(d, get_settings().structure_name)
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{d["reference"]}.pdf"'},
    )


@router.post("/fiches-detention/{fiche_id}/signer", response_model=DetentionOut, tags=["Fiches de détention"])
async def sign_fiche(
    fiche_id: int,
    date_signature: str | None = Form(None),
    fichier: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Marque la fiche « signée » (date du jour par defaut) ; scan du document signe facultatif."""
    signed_on = None
    if date_signature and date_signature.strip():
        try:
            signed_on = date.fromisoformat(date_signature.strip())
        except ValueError as exc:
            raise UnprocessableError("Date invalide (AAAA-MM-JJ).", field="date_signature") from exc
    return await fiche_service.sign(db, fiche_id, signed_on, fichier if fichier and fichier.filename else None)


@router.post("/fiches-detention/{fiche_id}/annuler-signature", response_model=DetentionOut, tags=["Fiches de détention"])
async def unsign_fiche(fiche_id: int, db: AsyncSession = Depends(get_db)):
    return await fiche_service.unsign(db, fiche_id)


@router.get("/fiches-detention/{fiche_id}/fichier-signe", tags=["Fiches de détention"])
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
