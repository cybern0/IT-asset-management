# Tableau de bord : JSON pour l'interface, exports PDF et Excel (meme calcul)
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.services import dashboard_export, dashboard_service

router = APIRouter()

Mois = Query(dashboard_service.MOIS_DEFAUT, ge=dashboard_service.MOIS_MIN, le=dashboard_service.MOIS_MAX,
             description="Nombre de mois affiches dans les graphiques d'evolution")

Jours = Query(None, ge=dashboard_service.JOURS_MIN, le=dashboard_service.JOURS_MAX,
              description="Evolution sur les n derniers jours (un point par jour) ; prioritaire sur `mois`")

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(content: bytes, media_type: str, ext: str, mois: int, jours: int | None) -> Response:
    periode = f"{jours}j" if jours else f"{mois}m"  # la periode choisie dans l'interface figure dans le nom du fichier
    name = f"tableau-de-bord-parc-{date.today().isoformat()}-{periode}.{ext}"
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db), mois: int = Mois, jours: int | None = Jours):
    return await dashboard_service.build(db, mois, jours)


@router.get("/export.pdf")
async def export_pdf(db: AsyncSession = Depends(get_db), mois: int = Mois, jours: int | None = Jours):
    return _attachment(dashboard_export.build_pdf(await dashboard_service.build(db, mois, jours)), "application/pdf", "pdf", mois, jours)


@router.get("/export.xlsx")
async def export_xlsx(db: AsyncSession = Depends(get_db), mois: int = Mois, jours: int | None = Jours):
    return _attachment(dashboard_export.build_xlsx(await dashboard_service.build(db, mois, jours)), XLSX, "xlsx", mois, jours)
