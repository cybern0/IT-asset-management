# Dossier d'attribution (fiche de detention) : les 6 etapes du processus
#   1 demande + validation du manager   2 selection d'un equipement en stock
#   3 generation de la fiche (automatique des la selection)
#   4 signature                         5 remise physique -> 6 materiel « Attribue » (affectation)
from datetime import date
from typing import Any

from fastapi import UploadFile
from sqlalchemy import Integer, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.errors import ConflictError, NotFoundError, UnprocessableError
from crud_api.models import (
    Affectation, Agent, CategorieMateriel, Direction, FicheDetention, Materiel, Service, Utilisateur,
)
from crud_api.schemas.fiche import ACCESSOIRES, AttributionCreate, RemiseIn
from crud_api.services import audit_service, file_store

_LOCK_KEY = 7240011  # verrou applicatif : numerotation sans doublon
REGULARISATION = "Régularisation"


# ----------------------------- etat du dossier -----------------------------
def etape_of(f: FicheDetention) -> int:
    """Etape a realiser (6 = termine : le materiel est attribue)."""
    if f.affectation_id:
        return 6
    if not f.valide_par:
        return 1
    if f.materiel_id is None:
        return 2
    if f.statut != "SIGNEE":
        return 4
    return 5


def etat_of(f: FicheDetention, a: Affectation | None) -> str:
    if f.cloture:
        return f.cloture
    if a is not None:
        return "ATTRIBUEE" if a.date_retour is None else "RENDUE"
    return "EN_COURS"


# ----------------------------- lecture -----------------------------
def _select():
    return (
        select(FicheDetention, Agent, Materiel, Affectation, Service, Direction, Utilisateur, CategorieMateriel)
        .join(Agent, Agent.id == FicheDetention.agent_id)
        .outerjoin(Materiel, Materiel.id == FicheDetention.materiel_id)
        .outerjoin(Affectation, Affectation.id == FicheDetention.affectation_id)
        .outerjoin(Service, Service.id == Agent.service_id)
        .outerjoin(Direction, Direction.id == Service.direction_id)
        .outerjoin(Utilisateur, Utilisateur.id == Affectation.cree_par)
        .outerjoin(CategorieMateriel, CategorieMateriel.id == FicheDetention.categorie_id)
    )


def _flat(row) -> dict[str, Any]:
    f, ag, m, a, s, d, u, cat = row
    return {
        "id": f.id, "reference": f.reference, "etape": etape_of(f), "etat": etat_of(f, a), "cree_le": f.cree_le,
        "categorie_id": f.categorie_id, "categorie_demandee": cat.libelle if cat else None, "besoin": f.besoin,
        "canal": f.canal, "reference_canal": f.reference_canal, "demandeur": f.demandeur,
        "date_demande": f.date_demande, "valide_par": f.valide_par, "date_validation": f.date_validation,
        "date_generation": f.date_generation,
        "statut": f.statut, "date_signature": f.date_signature, "mode_signature": f.mode_signature,
        "signe_par": f.signe_par, "a_fichier_signe": bool(f.fichier_signe_chemin),
        "date_remise": f.date_remise, "etat_constate": f.etat_constate,
        "accessoires": [x for x in (f.accessoires or "").split(",") if x],
        "accessoires_autre": f.accessoires_autre, "observations_remise": f.observations_remise,
        "affectation_id": f.affectation_id, "date_retour": a.date_retour if a else None,
        "etat_retour": a.etat_retour if a else None, "observations": a.observations if a else None,
        "saisi_par": u.nom_utilisateur if u else None, "cloture": f.cloture, "motif_cloture": f.motif_cloture,
        "materiel_id": m.id if m else None, "materiel_code": m.code_inventaire if m else None,
        "materiel_designation": m.designation if m else None,
        "materiel_categorie_code": m.categorie.code if m else None,
        "materiel_categorie": m.categorie.libelle if m else None,
        "materiel_marque": m.marque if m else None, "materiel_modele": m.modele if m else None,
        "materiel_serie": m.numero_serie if m else None,
        "materiel_caracteristiques": m.caracteristiques if m else None,
        "materiel_etat": m.etat if m else None, "materiel_statut": m.statut if m else None,
        "materiel_localisation": m.localisation if m else None, "materiel_a_image": bool(m and m.image_chemin),
        "agent_id": ag.id, "agent_matricule": ag.matricule, "agent_nom": ag.nom, "agent_prenom": ag.prenom,
        "agent_fonction": ag.fonction, "agent_email": ag.email,
        "service_nom": s.nom if s else None, "service_site": s.site if s else None,
        "direction_nom": d.nom if d else None,
    }


async def list_detentions(db: AsyncSession, *, limit: int = 5000) -> list[dict[str, Any]]:
    rows = (await db.execute(_select().order_by(FicheDetention.id.desc()).limit(limit))).unique().all()
    return [_flat(r) for r in rows]


async def get_detention(db: AsyncSession, fiche_id: int) -> dict[str, Any]:
    row = (
        await db.execute(_select().where(FicheDetention.id == fiche_id).execution_options(populate_existing=True))
    ).unique().first()
    if row is None:
        raise NotFoundError("Dossier d’attribution introuvable.")
    return _flat(row)


async def _fiche(db: AsyncSession, fiche_id: int) -> FicheDetention:
    fiche = await db.get(FicheDetention, fiche_id, populate_existing=True)
    if fiche is None:
        raise NotFoundError("Dossier d’attribution introuvable.")
    return fiche


def _not_closed(f: FicheDetention) -> None:
    if f.cloture:
        raise ConflictError(f"Ce dossier est clôturé ({'refusé' if f.cloture == 'REFUSEE' else 'annulé'}).")


def _open(f: FicheDetention) -> None:
    _not_closed(f)
    if f.affectation_id:
        raise ConflictError("Ce dossier est terminé : le matériel est déjà attribué.")


async def _next_reference(db: AsyncSession) -> str:
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    prefix = f"FD-{date.today().year}-"
    last = await db.scalar(
        select(func.max(cast(func.substr(FicheDetention.reference, len(prefix) + 1), Integer))).where(
            FicheDetention.reference.like(prefix + "%")
        )
    )
    return f"{prefix}{(last or 0) + 1:04d}"


async def _done(db: AsyncSession, fiche: FicheDetention, action: str, details: dict | None = None) -> dict[str, Any]:
    await audit_service.record(db, action, "fiche_detention", fiche.id, details)
    await db.commit()
    return await get_detention(db, fiche.id)


# ----------------------------- etape 1 : demande -----------------------------
async def create_request(db: AsyncSession, data: AttributionCreate) -> dict[str, Any]:
    agent = await db.get(Agent, data.agent_id)
    if agent is None or not agent.actif:
        raise UnprocessableError("Agent introuvable ou inactif.", field="agent_id")
    if data.categorie_id is not None and await db.get(CategorieMateriel, data.categorie_id) is None:
        raise UnprocessableError("Catégorie introuvable.", field="categorie_id")
    fiche = FicheDetention(
        reference=await _next_reference(db), agent_id=data.agent_id, categorie_id=data.categorie_id,
        besoin=data.besoin, canal=data.canal, reference_canal=data.reference_canal, demandeur=data.demandeur,
        date_demande=data.date_demande or date.today(),
    )
    if data.valide_par:
        fiche.valide_par = data.valide_par
        fiche.date_validation = fiche.date_demande
    db.add(fiche)
    await db.flush()
    return await _done(db, fiche, "CREATE", {"reference": fiche.reference})


async def validate(db: AsyncSession, fiche_id: int, valide_par: str, on: date | None) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _open(f)
    if f.valide_par:
        raise ConflictError("Cette demande est déjà validée.")
    on = on or date.today()
    if on < f.date_demande:
        raise UnprocessableError("La validation ne peut pas précéder la demande.", field="date_validation")
    f.valide_par, f.date_validation = valide_par, on
    return await _done(db, f, "VALIDATE", {"valide_par": valide_par})


async def refuse(db: AsyncSession, fiche_id: int, motif: str | None) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _open(f)
    if f.valide_par:
        raise ConflictError("Cette demande est déjà validée : utilisez « Annuler le dossier ».")
    f.cloture, f.motif_cloture = "REFUSEE", motif
    return await _done(db, f, "REFUSE", {"motif": motif})


async def cancel(db: AsyncSession, fiche_id: int, motif: str | None) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _open(f)
    f.cloture, f.motif_cloture = "ANNULEE", motif
    return await _done(db, f, "CANCEL", {"motif": motif})


# ----------------------------- etapes 2-3 : selection + fiche -----------------------------
async def select_equipment(db: AsyncSession, fiche_id: int, materiel_id: int) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _open(f)
    if not f.valide_par:
        raise ConflictError("La demande doit d’abord être validée par le manager (étape 1).")
    if f.materiel_id == materiel_id:
        return await get_detention(db, fiche_id)
    if f.statut == "SIGNEE":
        raise ConflictError("La fiche est signée : annulez la signature avant de changer d’équipement.")
    m = await db.get(Materiel, materiel_id)
    if m is None:
        raise UnprocessableError("Matériel introuvable.", field="materiel_id")
    if m.statut != "EN_STOCK":
        raise ConflictError(f"Ce matériel n’est pas disponible en stock (statut : {m.statut}).", field="materiel_id")
    other = await db.scalar(
        select(FicheDetention.reference).where(
            FicheDetention.materiel_id == materiel_id, FicheDetention.id != f.id,
            FicheDetention.affectation_id.is_(None), FicheDetention.cloture.is_(None),
        )
    )
    if other:
        raise ConflictError(f"Ce matériel est déjà réservé par le dossier {other}.", field="materiel_id")
    f.materiel_id = materiel_id
    f.date_generation = date.today()  # etape 3 : la fiche est generee automatiquement
    return await _done(db, f, "SELECT_EQUIPMENT", {"materiel_id": materiel_id})


# ----------------------------- etape 4 : signature -----------------------------
async def sign(
    db: AsyncSession, fiche_id: int, signed_on: date | None, mode: str, signe_par: str | None, scan: UploadFile | None
) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _not_closed(f)
    if f.materiel_id is None:
        raise ConflictError("Sélectionnez d’abord un équipement (étape 2) : la fiche n’est pas encore générée.")
    if mode not in ("MANUSCRITE", "ELECTRONIQUE"):
        raise UnprocessableError("Mode de signature invalide.", field="mode_signature")
    signed_on = signed_on or date.today()
    if signed_on < f.date_demande:
        raise UnprocessableError("La signature ne peut pas précéder la demande.", field="date_signature")

    old_scan = f.fichier_signe_chemin
    if scan is not None:
        f.fichier_signe_chemin = await file_store.save(
            scan, "fiches", f.reference, file_store.SCAN_TYPES, get_settings().max_scan_mb
        )
    f.statut, f.date_signature, f.mode_signature, f.signe_par = "SIGNEE", signed_on, mode, signe_par
    out = await _done(db, f, "SIGN", {"date_signature": signed_on.isoformat(), "mode": mode, "scan": scan is not None})
    if scan is not None:
        file_store.remove(old_scan)
    return out


async def unsign(db: AsyncSession, fiche_id: int) -> dict[str, Any]:
    f = await _fiche(db, fiche_id)
    _not_closed(f)
    if f.statut != "SIGNEE":
        raise ConflictError("Cette fiche n’est pas signée.")
    old_scan = f.fichier_signe_chemin
    f.statut, f.date_signature, f.mode_signature, f.signe_par, f.fichier_signe_chemin = (
        "NON_SIGNEE", None, None, None, None,
    )
    out = await _done(db, f, "UNSIGN")
    file_store.remove(old_scan)
    return out


async def scan_path(db: AsyncSession, fiche_id: int) -> str:
    f = await _fiche(db, fiche_id)
    if not f.fichier_signe_chemin:
        raise NotFoundError("Aucun scan enregistré pour cette fiche.")
    return f.fichier_signe_chemin


# ----------------------------- etapes 5-6 : remise + attribution -----------------------------
async def hand_over(db: AsyncSession, fiche_id: int, data: RemiseIn) -> dict[str, Any]:
    from crud_api.schemas.materiel import AffectationCreate  # import tardif : evite le cycle de modules
    from crud_api.services.materiel_service import affectation_service

    f = await _fiche(db, fiche_id)
    _open(f)
    if f.materiel_id is None:
        raise ConflictError("Sélectionnez d’abord un équipement (étape 2).")
    if f.statut != "SIGNEE":
        raise ConflictError("La fiche doit être signée avant la remise du matériel (étape 4).")
    remise = data.date_remise or date.today()
    if f.date_signature and remise < f.date_signature:
        raise UnprocessableError("La remise ne peut pas précéder la signature.", field="date_remise")
    m = await db.get(Materiel, f.materiel_id)
    etat = data.etat_constate or (m.etat if m and m.etat in ("NEUF", "BON", "A_REPARER") else "BON")

    f.date_remise, f.etat_constate = remise, etat
    f.accessoires = ",".join(a for a in ACCESSOIRES if a in data.accessoires) or None
    f.accessoires_autre, f.observations_remise = data.accessoires_autre, data.observations
    await db.flush()
    # etape 6 : l'affectation passe le materiel a « Attribue » ; son hook rattache cette fiche
    await affectation_service.create(
        db,
        AffectationCreate(
            materiel_id=f.materiel_id, agent_id=f.agent_id, date_remise=remise, etat_remise=etat,
            observations=data.observations,
        ),
    )
    return await get_detention(db, fiche_id)


# ----------------------------- lien avec les affectations -----------------------------
async def attach_or_create(db: AsyncSession, a: Affectation) -> FicheDetention:
    """Appele a la creation d'une affectation : rattache le dossier en cours (circuit normal),
    sinon cree un dossier de regularisation (affectation saisie directement). Sans commit."""
    fiche = await db.scalar(
        select(FicheDetention).where(
            FicheDetention.materiel_id == a.materiel_id, FicheDetention.agent_id == a.agent_id,
            FicheDetention.affectation_id.is_(None), FicheDetention.cloture.is_(None),
        )
    )
    if fiche is not None:
        fiche.affectation_id = a.id
        await db.flush()
        return fiche
    m = await db.get(Materiel, a.materiel_id)
    fiche = FicheDetention(
        reference=await _next_reference(db), agent_id=a.agent_id, materiel_id=a.materiel_id,
        affectation_id=a.id, categorie_id=m.categorie_id if m else None,
        besoin="Régularisation (affectation saisie hors circuit de demande)", date_demande=a.date_remise,
        valide_par=REGULARISATION, date_validation=a.date_remise, date_generation=a.date_remise,
        date_remise=a.date_remise,
        etat_constate=a.etat_remise if a.etat_remise in ("NEUF", "BON", "A_REPARER") else None,
    )
    db.add(fiche)
    await db.flush()
    await audit_service.record(db, "CREATE", "fiche_detention", fiche.id, {"reference": fiche.reference})
    return fiche


async def get_by_affectation(db: AsyncSession, affectation_id: int) -> dict[str, Any]:
    """Dossier d'une affectation ; cree a la demande pour une affectation inseree directement en SQL."""
    a = await db.get(Affectation, affectation_id)
    if a is None:
        raise NotFoundError("Affectation introuvable.")
    fiche = await db.scalar(select(FicheDetention).where(FicheDetention.affectation_id == affectation_id))
    if fiche is None:
        fiche = await attach_or_create(db, a)
        await db.commit()
    return await get_detention(db, fiche.id)
