# Affectation directe (transfert d'un materiel deja detenu) et listes d'options des formulaires.
# Un seul role existe (ADMIN, tous les droits) : le depositaire comptable fait chaque geste lui-meme ; le compte qui
# agit est enregistre sur la fiche. Les anciennes etapes multi-utilisateurs (approbation, signatures separees,
# notifications) ont ete retirees : le pas a pas des dossiers est dans fiche_service.
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.deps import Principal
from crud_api.core.errors import ConflictError, UnprocessableError
from crud_api.models import Affectation, Agent, CategorieMateriel, FicheDetention, Materiel
from crud_api.schemas.circuit import TransfertCreate
from crud_api.services import fiche_service
from crud_api.services.materiel_service import affectation_service


def _actor(p: Principal) -> int | None:
    return p.user.id if p.user else None


async def transfer(db: AsyncSession, p: Principal, data: TransfertCreate) -> Affectation:
    """AFFECTATION : le depositaire comptable retire un materiel a son detenteur et l'affecte a un autre agent, en une
    seule operation : l'ancienne affectation est close, la nouvelle ouverte et un dossier de transfert est garde.
    Tout est valide ensemble, ou rien."""
    m = await db.get(Materiel, data.materiel_id, populate_existing=True)
    if m is None:
        raise UnprocessableError("Matériel introuvable.", field="materiel_id")
    nouveau = await db.get(Agent, data.agent_id)
    if nouveau is None or not nouveau.actif:
        raise UnprocessableError("Agent introuvable ou inactif.", field="agent_id")
    old = await db.scalar(select(Affectation).where(
        Affectation.materiel_id == m.id, Affectation.date_retour.is_(None)).with_for_update())
    if m.statut != "ATTRIBUE" or old is None:
        raise ConflictError("Ce matériel n’est détenu par personne : utilisez une attribution.", field="materiel_id")
    if old.agent_id == nouveau.id:
        raise ConflictError("Cet agent détient déjà ce matériel.", field="agent_id")
    reserve = await db.scalar(select(FicheDetention.reference).where(
        FicheDetention.materiel_id == m.id, FicheDetention.affectation_id.is_(None), FicheDetention.cloture.is_(None)))
    if reserve:
        raise ConflictError(f"Ce matériel est déjà réservé par le dossier {reserve}.", field="materiel_id")
    on = data.date or date.today()
    if on < old.date_remise:
        raise UnprocessableError("La date ne peut pas précéder la remise à l’ancien détenteur.", field="date")
    etat = data.etat or (m.etat if m.etat in ("NEUF", "BON", "A_REPARER") else "BON")
    ancien = await db.get(Agent, old.agent_id) if old.agent_id else None
    ancien_nom = f"{ancien.prenom} {ancien.nom}" if ancien else (old.agent_nom or "ancien détenteur")

    # 1) l'ancienne affectation est close, le materiel est libere ...
    old.date_retour, old.etat_retour = on, etat
    old.observations = f"{old.observations + chr(10) if old.observations else ''}Réaffecté à {nouveau.prenom} {nouveau.nom}"
    m.statut = "EN_STOCK"
    await db.flush()
    # 2) ... puis immediatement affecte au nouvel agent
    nouvelle = Affectation(
        materiel_id=m.id, agent_id=nouveau.id, agent_matricule=nouveau.matricule, agent_nom=f"{nouveau.prenom} {nouveau.nom}",
        date_remise=on, etat_remise=etat, observations=data.observations, cree_par=_actor(p),
    )
    m.statut = "ATTRIBUE"
    db.add(nouvelle)
    await db.flush()
    # 3) dossier de transfert : retrouvable dans l’onglet Affectations
    fiche = await fiche_service.attach_or_create(db, nouvelle)
    fiche.type_demande, fiche.ancien_agent_id, fiche.ancienne_affectation_id = "AFFECTATION", old.agent_id, old.id
    fiche.besoin = f"Affectation directe : matériel retiré à {ancien_nom}"
    fiche.valide_par = p.user.nom_utilisateur if p.user else "Dépositaire comptable"
    await db.flush()
    await db.commit()
    return await affectation_service.get(db, nouvelle.id)


async def options(db: AsyncSession, p: Principal) -> dict[str, Any]:
    cats = (await db.execute(select(CategorieMateriel).order_by(CategorieMateriel.id))).scalars().all()
    stock, detenus = [], []
    if p.has("demande.approuver"):
        rows = (await db.scalars(select(Materiel).where(Materiel.statut == "EN_STOCK").order_by(Materiel.id).limit(2000))).all()
        stock = [{"id": m.id, "code_inventaire": m.code_inventaire, "designation": m.designation, "categorie_id": m.categorie_id} for m in rows]
    if p.has("affectation.transferer"):
        held = await db.execute(
            select(Materiel, Agent).join(Affectation, Affectation.materiel_id == Materiel.id)
            .join(Agent, Agent.id == Affectation.agent_id)
            .where(Materiel.statut == "ATTRIBUE", Affectation.date_retour.is_(None)).order_by(Materiel.id).limit(2000))
        detenus = [{"id": m.id, "code_inventaire": m.code_inventaire, "designation": m.designation, "categorie_id": m.categorie_id,
                    "detenteur_id": a.id, "detenteur": f"{a.prenom} {a.nom}"} for m, a in held.all()]
    return {"categories": [{"id": c.id, "code": c.code, "libelle": c.libelle} for c in cats], "stock": stock, "detenus": detenus}

