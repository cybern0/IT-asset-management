# Dossier d'attribution (fiche de detention) : les 6 etapes du processus
#   1 demande + validation du manager   2 selection d'un equipement en stock
#   3 generation de la fiche (automatique des la selection)
#   4 signature                         5 remise physique -> 6 materiel « Attribue » (affectation)
#
# Les etapes 1, 4 et 5 sont des gestes humains (validation, signature, remise) qui se font hors de l'application :
# elle se contente d'enregistrer qu'ils ont eu lieu. D'ou trois actions seulement : avancer (l'etape en cours est faite),
# reculer (on defait la derniere etape), clore (refus ou annulation). L'etape en cours est deduite des donnees.
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Integer, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import ConflictError, NotFoundError, UnprocessableError
from crud_api.models import (
    Affectation, Agent, CategorieMateriel, Direction, FicheDetention, Materiel, Service, Utilisateur,
)
from crud_api.schemas.fiche import ACCESSOIRES, AttributionCreate, AvancerIn, SignatureIn
from crud_api.services import audit_service

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


def phase_of(f: FicheDetention) -> str:
    """Phase du circuit de demande (meme logique que la vue SQL v_circuit_demande). Tolere les dossiers du circuit
    historique : valide_par vaut approbation, statut SIGNEE vaut les deux signatures, une affectation vaut remise."""
    signed = f.statut == "SIGNEE"
    if f.cloture:
        return "CLOTUREE"
    if not (f.approuve_le or f.valide_par) or f.materiel_id is None:
        return "A_APPROUVER"
    if not (f.signature_agent_le or signed):
        return "A_SIGNER_AGENT"
    if not (f.signature_chef_le or signed):
        return "A_SIGNER_CHEF"
    if not (f.date_remise or f.affectation_id):
        return "A_REMETTRE"
    return "TERMINEE" if f.reception_approuvee_le else "A_APPROUVER_RECEPTION"


# Un seul role : ADMIN fait toutes les etapes, au nom de l'agent et du chef de service (circuit_service, parc_14.sql)
ROLE_ATTENDU = {
    "A_APPROUVER": "ADMIN", "A_SIGNER_AGENT": "ADMIN", "A_SIGNER_CHEF": "ADMIN",
    "A_REMETTRE": "ADMIN", "A_APPROUVER_RECEPTION": "ADMIN",
}


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
        .outerjoin(Agent, Agent.id == FicheDetention.agent_id)  # l'agent peut avoir ete supprime
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
        "signe_par": f.signe_par, "signature_modifiee_par": f.signature_modifiee_par,
        "signature_modifiee_le": f.signature_modifiee_le,
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
        "materiel_provenance": m.provenance if m else None,
        "materiel_provenance_detail": m.provenance_detail if m else None,
        "materiel_date_acquisition": m.date_acquisition if m else None,
        "type_demande": f.type_demande, "ancien_agent_id": f.ancien_agent_id, "phase": phase_of(f), "role_attendu": ROLE_ATTENDU.get(phase_of(f)),
        "approuve_le": f.approuve_le, "motif_refus": f.motif_refus, "signature_agent_le": f.signature_agent_le,
        "signature_chef_le": f.signature_chef_le, "reception_approuvee_le": f.reception_approuvee_le,
        "agent_service_id": s.id if s else None, "chef_agent_id": s.chef_agent_id if s else None,
        # agent supprime de la base (ag is None) : on garde le nom memorise sur le dossier
        "agent_id": ag.id if ag else None, "agent_matricule": ag.matricule if ag else (f.agent_matricule or "—"),
        "agent_nom": ag.nom if ag else (f.agent_nom or "Agent supprimé"), "agent_prenom": ag.prenom if ag else "",
        "agent_fonction": ag.fonction if ag else None, "agent_email": ag.email if ag else None,
        "agent_telephone": f.telephone or (ag.telephone if ag else None), "agent_whatsapp": f.whatsapp or (ag.whatsapp if ag else None),
        "agent_adresse_domicile_exacte": f.adresse_domicile_exacte or (ag.adresse_domicile_exacte if ag else None),
        "service_nom": s.nom if s else None, "service_site": s.site if s else None,
        "direction_nom": d.nom if d else None,
    }


async def list_detentions(db: AsyncSession, *, limit: int = 5000) -> list[dict[str, Any]]:
    rows = (await db.execute(_select().order_by(FicheDetention.id.desc()).limit(limit))).unique().all()
    return [_flat(r) for r in rows]


async def category_types(db: AsyncSession) -> list[tuple[str, str]]:
    """(code, libelle) des categories du dictionnaire, dans l'ordre : options de la ligne « Type d'equipement »."""
    rows = await db.execute(select(CategorieMateriel.code, CategorieMateriel.libelle).order_by(CategorieMateriel.id))
    return [(code, libelle) for code, libelle in rows.all()]


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


def _dt(d: date | None) -> datetime | None:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None


def _not_closed(f: FicheDetention) -> None:
    if f.cloture:
        raise ConflictError(f"Ce dossier est clôturé ({'refusé' if f.cloture == 'REFUSEE' else 'annulé'}).")


def _open(f: FicheDetention) -> None:
    _not_closed(f)
    if f.affectation_id:
        raise ConflictError("Ce dossier est terminé : le matériel est déjà attribué.")


async def _next_reference(db: AsyncSession) -> str:
    if db.get_bind().dialect.name == "postgresql":
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


# ----------------------------- etape suivante / etape precedente / cloture -----------------------------
async def _reserve(db: AsyncSession, f: FicheDetention, materiel_id: int | None) -> None:
    """Etape 2 : l'equipement doit etre en stock et ne pas etre reserve par un autre dossier ouvert."""
    if materiel_id is None:
        raise UnprocessableError("Choisissez l’équipement à attribuer.", field="materiel_id")
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


async def advance(db: AsyncSession, fiche_id: int, data: AvancerIn) -> dict[str, Any]:
    """L'etape en cours est faite : on l'enregistre et le dossier passe a la suivante."""
    f = await _fiche(db, fiche_id)
    _open(f)
    step, on = etape_of(f), data.date or date.today()

    if step == 1:  # le manager a valide la demande
        if not data.valide_par:
            raise UnprocessableError("Indiquez le manager qui a validé la demande.", field="valide_par")
        f.valide_par, f.date_validation = data.valide_par, on
        return await _done(db, f, "VALIDATE", {"valide_par": data.valide_par})

    if step == 2:  # equipement choisi : la fiche est generee (etape 3, automatique)
        await _reserve(db, f, data.materiel_id)
        f.materiel_id, f.date_generation = data.materiel_id, date.today()
        return await _done(db, f, "SELECT_EQUIPMENT", {"materiel_id": data.materiel_id})

    if step == 4:  # la fiche a ete signee (papier ou electronique)
        f.statut, f.date_signature = "SIGNEE", on
        f.mode_signature, f.signe_par = data.mode_signature or "MANUSCRITE", data.signe_par
        return await _done(db, f, "SIGN", {"date_signature": on.isoformat(), "mode": f.mode_signature})

    return await _hand_over(db, f, data, on)  # etape 5 : le materiel a ete remis


async def _hand_over(db: AsyncSession, f: FicheDetention, data: AvancerIn, remise: date) -> dict[str, Any]:
    """Etapes 5 et 6 : remise enregistree, puis creation de l'affectation (materiel « Attribue »)."""
    from crud_api.schemas.materiel import AffectationCreate  # import tardif : evite le cycle de modules
    from crud_api.services.materiel_service import affectation_service

    m = await db.get(Materiel, f.materiel_id)
    etat = data.etat_constate or (m.etat if m and m.etat in ("NEUF", "BON", "A_REPARER") else "BON")
    f.date_remise, f.etat_constate = remise, etat
    f.accessoires = ",".join(a for a in ACCESSOIRES if a in data.accessoires) or None
    f.accessoires_autre, f.observations_remise = data.accessoires_autre, data.observations
    await db.flush()
    # l'affectation passe le materiel a « Attribue » ; son hook rattache ce dossier
    await affectation_service.create(
        db,
        AffectationCreate(
            materiel_id=f.materiel_id, agent_id=f.agent_id, date_remise=remise, etat_remise=etat,
            observations=data.observations,
        ),
    )
    return await get_detention(db, f.id)


async def set_signature(db: AsyncSession, fiche_id: int, data: SignatureIn) -> dict[str, Any]:
    """L'administrateur indique a la main si la fiche est signee ou doit encore l'etre. Possible des que la fiche est
    generee (equipement choisi) et a tout moment ensuite, meme apres la remise : une signature peut arriver en retard
    ou etre a refaire. Qui l'a fixee et quand est conserve sur le dossier."""
    f = await _fiche(db, fiche_id)
    _not_closed(f)
    if f.materiel_id is None:
        raise ConflictError("La fiche n’est générée qu’une fois l’équipement choisi : son état de signature ne peut pas encore être renseigné.")
    if data.signee:
        f.statut, f.date_signature = "SIGNEE", data.date or date.today()
        f.mode_signature, f.signe_par = data.mode_signature or "MANUSCRITE", data.signe_par
    else:
        f.statut, f.date_signature, f.mode_signature, f.signe_par = "NON_SIGNEE", None, None, None
    actor_id = db.info.get("actor_id")
    actor = await db.get(Utilisateur, actor_id) if actor_id else None
    f.signature_modifiee_par = actor.nom_utilisateur if actor else None
    f.signature_modifiee_le = datetime.now(timezone.utc)
    return await _done(db, f, "SET_SIGNATURE", {"signee": data.signee, "date_signature": f.date_signature and f.date_signature.isoformat()})


async def back(db: AsyncSession, fiche_id: int) -> dict[str, Any]:
    """On defait la derniere etape faite (erreur de saisie, signature a refaire, autre equipement...)."""
    f = await _fiche(db, fiche_id)
    _not_closed(f)
    if f.affectation_id:
        raise ConflictError("Le matériel est déjà attribué : enregistrez son retour dans Affectations.")
    step = etape_of(f)
    if step == 1:
        raise ConflictError("Ce dossier est déjà à la première étape.")
    if step == 2:
        f.valide_par = f.date_validation = None
        return await _done(db, f, "UNVALIDATE")
    if step == 4:  # on retire l'equipement : il redevient libre pour un autre dossier
        f.materiel_id = f.date_generation = None
        return await _done(db, f, "UNSELECT_EQUIPMENT")
    f.statut, f.date_signature, f.mode_signature, f.signe_par = "NON_SIGNEE", None, None, None  # etape 5
    return await _done(db, f, "UNSIGN")


async def close(db: AsyncSession, fiche_id: int, motif: str | None) -> dict[str, Any]:
    """Fin du dossier avant l'attribution : refuse tant que le manager n'a pas valide, annule ensuite."""
    f = await _fiche(db, fiche_id)
    _open(f)
    f.cloture = "ANNULEE" if f.valide_par else "REFUSEE"
    f.motif_cloture = motif
    return await _done(db, f, "CANCEL" if f.valide_par else "REFUSE", {"motif": motif})


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
        date_remise=a.date_remise, approuve_le=_dt(a.date_remise), signature_agent_le=_dt(a.date_remise),
        signature_chef_le=_dt(a.date_remise), reception_approuvee_le=_dt(a.date_remise),
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
