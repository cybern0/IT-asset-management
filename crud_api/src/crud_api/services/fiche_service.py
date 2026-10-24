# Fiche de detention : creation, signature, vues croisees materiel x agent
from datetime import date
from typing import Any

from fastapi import UploadFile
from sqlalchemy import Integer, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.errors import ConflictError, NotFoundError, UnprocessableError
from crud_api.models import Affectation, Agent, Direction, FicheDetention, Materiel, Service, Utilisateur
from crud_api.services import audit_service, file_store

_LOCK_KEY = 7240011  # verrou applicatif : numerotation sans doublon


async def _next_reference(db: AsyncSession) -> str:
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    prefix = f"FD-{date.today().year}-"
    last = await db.scalar(
        select(func.max(cast(func.substr(FicheDetention.reference, len(prefix) + 1), Integer))).where(
            FicheDetention.reference.like(prefix + "%")
        )
    )
    return f"{prefix}{(last or 0) + 1:04d}"


async def ensure_for_affectation(db: AsyncSession, affectation_id: int) -> FicheDetention:
    """Cree la fiche (NON_SIGNEE) si elle n'existe pas encore. Ne valide pas la transaction."""
    fiche = await db.scalar(select(FicheDetention).where(FicheDetention.affectation_id == affectation_id))
    if fiche is None:
        fiche = FicheDetention(affectation_id=affectation_id, reference=await _next_reference(db))
        db.add(fiche)
        await db.flush()
        await audit_service.record(db, "CREATE", "fiche_detention", fiche.id, {"reference": fiche.reference})
    return fiche


def _select():
    return (
        select(FicheDetention, Affectation, Materiel, Agent, Service, Direction, Utilisateur)
        .join(Affectation, Affectation.id == FicheDetention.affectation_id)
        .join(Materiel, Materiel.id == Affectation.materiel_id)
        .join(Agent, Agent.id == Affectation.agent_id)
        .outerjoin(Service, Service.id == Agent.service_id)
        .outerjoin(Direction, Direction.id == Service.direction_id)
        .outerjoin(Utilisateur, Utilisateur.id == Affectation.cree_par)
    )


def _flat(row) -> dict[str, Any]:
    f, a, m, ag, s, d, u = row
    return {
        "id": f.id, "reference": f.reference, "statut": f.statut,
        "date_signature": f.date_signature, "a_fichier_signe": bool(f.fichier_signe_chemin),
        "cree_le": f.cree_le,
        "affectation_id": a.id, "date_remise": a.date_remise, "date_retour": a.date_retour,
        "en_cours": a.date_retour is None, "etat_remise": a.etat_remise, "etat_retour": a.etat_retour,
        "observations": a.observations, "saisi_par": u.nom_utilisateur if u else None,
        "materiel_id": m.id, "materiel_code": m.code_inventaire, "materiel_designation": m.designation,
        "materiel_categorie_code": m.categorie.code, "materiel_categorie": m.categorie.libelle,
        "materiel_marque": m.marque, "materiel_modele": m.modele, "materiel_serie": m.numero_serie,
        "materiel_caracteristiques": m.caracteristiques, "materiel_etat": m.etat,
        "materiel_statut": m.statut, "materiel_localisation": m.localisation,
        "materiel_a_image": bool(m.image_chemin),
        "agent_id": ag.id, "agent_matricule": ag.matricule, "agent_nom": ag.nom, "agent_prenom": ag.prenom,
        "agent_fonction": ag.fonction, "agent_email": ag.email,
        "service_nom": s.nom if s else None, "service_site": s.site if s else None,
        "direction_nom": d.nom if d else None,
    }


async def list_detentions(db: AsyncSession, *, limit: int = 5000) -> list[dict[str, Any]]:
    rows = (await db.execute(_select().order_by(FicheDetention.id.desc()).limit(limit))).unique().all()
    return [_flat(r) for r in rows]


async def get_detention(db: AsyncSession, fiche_id: int) -> dict[str, Any]:
    row = (await db.execute(_select().where(FicheDetention.id == fiche_id))).unique().first()
    if row is None:
        raise NotFoundError("Fiche de détention introuvable.")
    return _flat(row)


async def get_by_affectation(db: AsyncSession, affectation_id: int) -> dict[str, Any]:
    """Fiche d'une affectation ; creee a la demande pour les affectations anterieures a parc_5.sql."""
    if await db.get(Affectation, affectation_id) is None:
        raise NotFoundError("Affectation introuvable.")
    fiche = await ensure_for_affectation(db, affectation_id)
    await db.commit()
    return await get_detention(db, fiche.id)


async def _fiche(db: AsyncSession, fiche_id: int) -> FicheDetention:
    fiche = await db.get(FicheDetention, fiche_id)
    if fiche is None:
        raise NotFoundError("Fiche de détention introuvable.")
    return fiche


async def sign(db: AsyncSession, fiche_id: int, signed_on: date | None, scan: UploadFile | None) -> dict[str, Any]:
    fiche = await _fiche(db, fiche_id)
    affectation = await db.get(Affectation, fiche.affectation_id)
    signed_on = signed_on or date.today()
    if affectation is not None and signed_on < affectation.date_remise:
        raise UnprocessableError("La signature ne peut pas précéder la remise.", field="date_signature")

    old_scan = fiche.fichier_signe_chemin
    if scan is not None:
        s = get_settings()
        fiche.fichier_signe_chemin = await file_store.save(
            scan, "fiches", fiche.reference, file_store.SCAN_TYPES, s.max_scan_mb
        )
    fiche.statut = "SIGNEE"
    fiche.date_signature = signed_on
    await audit_service.record(
        db, "SIGN", "fiche_detention", fiche.id, {"date_signature": signed_on.isoformat(), "scan": scan is not None}
    )
    await db.commit()
    if scan is not None:
        file_store.remove(old_scan)
    return await get_detention(db, fiche_id)


async def unsign(db: AsyncSession, fiche_id: int) -> dict[str, Any]:
    fiche = await _fiche(db, fiche_id)
    if fiche.statut != "SIGNEE":
        raise ConflictError("Cette fiche n’est pas signée.")
    old_scan = fiche.fichier_signe_chemin
    fiche.statut = "NON_SIGNEE"
    fiche.date_signature = None
    fiche.fichier_signe_chemin = None
    await audit_service.record(db, "UNSIGN", "fiche_detention", fiche.id, None)
    await db.commit()
    file_store.remove(old_scan)
    return await get_detention(db, fiche_id)


async def scan_path(db: AsyncSession, fiche_id: int) -> str:
    fiche = await _fiche(db, fiche_id)
    if not fiche.fichier_signe_chemin:
        raise NotFoundError("Aucun scan enregistré pour cette fiche.")
    return fiche.fichier_signe_chemin
