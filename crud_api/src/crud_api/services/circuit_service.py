# Circuit de demande (RBAC) :
#   1 demande (attribution ou affectation)           2 le depositaire comptable approuve, choisit le materiel, met la base a jour
#   3 signature de l'agent, puis du chef de son service     4 remise du materiel   5 approbation de la reception par le chef de service
# Un seul role existe (ADMIN, tous les droits) : un administrateur fait chaque etape au nom de l'agent ou du chef de
# service (le compte qui agit est enregistre sur la fiche).
# Chaque etape prepare les notifications (liens mail / SMS / WhatsApp) de la personne suivante.
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.deps import Principal
from crud_api.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from crud_api.models import Affectation, Agent, CategorieMateriel, FicheDetention, Materiel, Notification, Service
from crud_api.schemas.circuit import ApprouverIn, DemandeCreate, TransfertCreate
from crud_api.schemas.fiche import AvancerIn
from crud_api.services import audit_service, fiche_service, notification_service
from crud_api.services.materiel_service import affectation_service

_now = lambda: datetime.now(timezone.utc)  # noqa: E731


def _actor(p: Principal) -> int | None:
    return p.user.id if p.user else None


def _actions(f: dict[str, Any], p: Principal) -> list[str]:
    phase, agent_id, chef = f["phase"], f["agent_id"], f["chef_agent_id"]
    me = p.agent_id
    on_behalf = p.open or p.has("demande.voir_toutes")  # ADMIN : agit au nom de l'agent ou du chef de service
    out: list[str] = []
    if phase == "A_APPROUVER" and p.has("demande.approuver"):
        # une AFFECTATION (retirer un materiel a son detenteur) demande en plus le droit de transfert
        out = ["approuver", "refuser"] if f["type_demande"] != "AFFECTATION" or p.has("affectation.transferer") else ["refuser"]
    elif phase == "A_SIGNER_AGENT" and p.has("fiche.signer_agent") and (on_behalf or me == agent_id):
        out = ["signer-agent"]
    elif phase == "A_SIGNER_CHEF" and p.has("fiche.signer_chef") and (on_behalf or (chef is not None and me == chef)):
        out = ["signer-chef"]
    elif phase == "A_REMETTRE" and p.has("fiche.remettre"):
        out = ["remettre"]
    elif phase == "A_APPROUVER_RECEPTION" and p.has("reception.approuver") and (on_behalf or (chef is not None and me == chef)):
        out = ["approuver-reception"]
    return out


async def _decorate(db: AsyncSession, rows: list[dict[str, Any]], p: Principal) -> list[dict[str, Any]]:
    ids = {r["chef_agent_id"] for r in rows if r["chef_agent_id"]}
    names = {}
    if ids:
        names = {a.id: f"{a.prenom} {a.nom}" for a in (await db.scalars(select(Agent).where(Agent.id.in_(ids)))).all()}
    old_ids = {r["ancien_agent_id"] for r in rows if r.get("ancien_agent_id")}
    olds = {}
    if old_ids:
        olds = {a.id: f"{a.prenom} {a.nom}" for a in (await db.scalars(select(Agent).where(Agent.id.in_(old_ids)))).all()}
    for r in rows:
        r["actions"] = _actions(r, p)
        r["chef_nom"] = names.get(r["chef_agent_id"])
        r["ancien_detenteur"] = olds.get(r.get("ancien_agent_id"))
    return rows


def _visible(r: dict[str, Any], p: Principal, chefs: set[int]) -> bool:
    if p.has("demande.voir_toutes"):
        return True
    me = p.agent_id
    if p.has("demande.voir_propres") and me is not None and r["agent_id"] == me:
        return True
    return p.has("demande.voir_service") and me is not None and r["chef_agent_id"] == me


async def list_demandes(db: AsyncSession, p: Principal) -> list[dict[str, Any]]:
    rows = [r for r in await fiche_service.list_detentions(db) if p.open or _visible(r, p, set())]
    return await _decorate(db, rows, p)


async def get_demande(db: AsyncSession, p: Principal, fiche_id: int) -> dict[str, Any]:
    row = await fiche_service.get_detention(db, fiche_id)
    if not (p.open or _visible(row, p, set())):
        raise ForbiddenError("Cette demande ne vous concerne pas.")
    return (await _decorate(db, [row], p))[0]


async def _load(db: AsyncSession, p: Principal, fiche_id: int, phase: str, action: str) -> tuple[FicheDetention, dict[str, Any]]:
    """Charge le dossier et verifie : phase attendue + droit de faire CE geste sur CE dossier."""
    f = await db.get(FicheDetention, fiche_id, populate_existing=True)
    if f is None:
        raise NotFoundError("Demande introuvable.")
    if fiche_service.phase_of(f) != phase:
        raise ConflictError("Cette étape n'est pas (ou plus) à faire pour cette demande.")
    flat = await fiche_service.get_detention(db, fiche_id)
    if action not in _actions(flat, p):
        raise ForbiddenError("Vous n'êtes pas la personne désignée pour cette étape.")
    return f, flat


async def _finish(db: AsyncSession, p: Principal, f: FicheDetention, flat: dict[str, Any], audit: str, details: dict | None = None) -> dict[str, Any]:
    await audit_service.record(db, audit, "fiche_detention", f.id, details)
    await db.flush()
    await notification_service.notify(db, f, fiche_service.phase_of(f), flat["chef_agent_id"], _actor(p))
    await db.commit()
    return await get_demande(db, p, f.id)


# ----------------------------- 1 : demande -----------------------------
async def create(db: AsyncSession, p: Principal, data: DemandeCreate) -> dict[str, Any]:
    agent_id = data.agent_id
    if not p.has("demande.voir_toutes"):  # agent standard : uniquement pour lui-meme
        if p.agent_id is None:
            raise UnprocessableError("Votre compte n'est lié à aucun agent : demandez à l'administrateur de le rattacher.")
        agent_id = p.agent_id
    if agent_id is None:
        raise UnprocessableError("Indiquez l'agent concerné.", field="agent_id")
    agent = await db.get(Agent, agent_id)
    if agent is None or not agent.actif:
        raise UnprocessableError("Agent introuvable ou inactif.", field="agent_id")
    if data.categorie_id is not None and await db.get(CategorieMateriel, data.categorie_id) is None:
        raise UnprocessableError("Catégorie introuvable.", field="categorie_id")
    f = FicheDetention(
        reference=await fiche_service._next_reference(db), agent_id=agent_id, categorie_id=data.categorie_id,
        besoin=data.besoin, canal=data.canal, reference_canal=data.reference_canal,
        demandeur=data.demandeur or f"{agent.prenom} {agent.nom}", date_demande=date.today(),
        type_demande=data.type_demande, demande_par=_actor(p),
    )
    db.add(f)
    await db.flush()
    service = await db.get(Service, agent.service_id) if agent.service_id else None
    flat = {"chef_agent_id": service.chef_agent_id if service else None}
    return await _finish(db, p, f, flat, "CREATE", {"reference": f.reference, "type": f.type_demande})


# ----------------------------- 2 : approbation par le depositaire comptable -----------------------------
async def approve(db: AsyncSession, p: Principal, fiche_id: int, data: ApprouverIn) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_APPROUVER", "approuver")
    if f.type_demande == "AFFECTATION":  # materiel DETENU par un autre agent : on le lui retirera a la remise
        old = await _reserve_held(db, f, data.materiel_id)
        f.ancien_agent_id, f.ancienne_affectation_id = old.agent_id, old.id
    else:  # ATTRIBUTION : materiel non affecte (en stock)
        await fiche_service._reserve(db, f, data.materiel_id)
    on = data.date or date.today()
    f.materiel_id, f.date_generation = data.materiel_id, date.today()
    f.valide_par = p.user.nom_utilisateur if p.user else "Dépositaire comptable"
    f.date_validation, f.approuve_le, f.approuve_par = on, _now(), _actor(p)
    return await _finish(db, p, f, flat, "APPROVE", {"materiel_id": data.materiel_id})


async def _reserve_held(db: AsyncSession, f: FicheDetention, materiel_id: int) -> Affectation:
    """Affectation : le materiel doit etre detenu par un AUTRE agent et libre de tout autre dossier ouvert."""
    m = await db.get(Materiel, materiel_id)
    if m is None:
        raise UnprocessableError("Matériel introuvable.", field="materiel_id")
    old = await db.scalar(select(Affectation).where(Affectation.materiel_id == materiel_id, Affectation.date_retour.is_(None)))
    if m.statut != "ATTRIBUE" or old is None:
        raise ConflictError("Ce matériel n’est détenu par personne : utilisez une attribution.", field="materiel_id")
    if old.agent_id == f.agent_id:
        raise ConflictError("Cet agent détient déjà ce matériel.", field="materiel_id")
    other = await db.scalar(select(FicheDetention.reference).where(
        FicheDetention.materiel_id == materiel_id, FicheDetention.id != f.id,
        FicheDetention.affectation_id.is_(None), FicheDetention.cloture.is_(None)))
    if other:
        raise ConflictError(f"Ce matériel est déjà réservé par le dossier {other}.", field="materiel_id")
    return old


async def refuse(db: AsyncSession, p: Principal, fiche_id: int, motif: str | None) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_APPROUVER", "refuser")
    f.cloture, f.motif_cloture, f.motif_refus = "REFUSEE", motif, motif
    return await _finish(db, p, f, flat, "REFUSE", {"motif": motif})


# ----------------------------- 3 : signatures (agent, puis chef de service) -----------------------------
async def sign_agent(db: AsyncSession, p: Principal, fiche_id: int) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_SIGNER_AGENT", "signer-agent")
    f.signature_agent_le, f.signature_agent_par = _now(), _actor(p)
    return await _finish(db, p, f, flat, "SIGN_AGENT")


async def sign_chef(db: AsyncSession, p: Principal, fiche_id: int) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_SIGNER_CHEF", "signer-chef")
    f.signature_chef_le, f.signature_chef_par = _now(), _actor(p)
    # nom du chef de service du demandeur ; a defaut (service sans chef), l'agent rattache au compte qui signe
    chef_id = flat["chef_agent_id"] or p.agent_id
    chef = await db.get(Agent, chef_id) if chef_id else None
    f.statut, f.date_signature, f.mode_signature = "SIGNEE", date.today(), "ELECTRONIQUE"
    f.signe_par = f"{chef.prenom} {chef.nom}" if chef else None
    return await _finish(db, p, f, flat, "SIGN_CHEF")


# ----------------------------- 4 : remise -----------------------------
async def hand_over(db: AsyncSession, p: Principal, fiche_id: int, data: AvancerIn) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_REMETTRE", "remettre")
    on = data.date or date.today()
    transfer = f.type_demande == "AFFECTATION" and f.ancienne_affectation_id is not None
    if transfer:  # le materiel est retire a son detenteur : l'ancienne affectation est close avant d'ouvrir la nouvelle
        old = await db.get(Affectation, f.ancienne_affectation_id, populate_existing=True)
        m = await db.get(Materiel, f.materiel_id, populate_existing=True)
        if old is None or old.date_retour is not None or old.materiel_id != f.materiel_id:
            raise ConflictError("Le matériel n’est plus chez son détenteur initial : refaites l’approbation.")
        if on < old.date_remise:
            raise UnprocessableError("La remise ne peut pas précéder la date de remise à l’ancien détenteur.", field="date")
        etat = data.etat_constate or (m.etat if m.etat in ("NEUF", "BON", "A_REPARER") else "BON")
        nouveau = await db.get(Agent, f.agent_id)
        old.date_retour, old.etat_retour = on, etat
        old.observations = f"{old.observations + chr(10) if old.observations else ''}Réaffecté à {nouveau.prenom} {nouveau.nom} ({f.reference})"
        m.statut = "EN_STOCK"  # libere pour la nouvelle affectation, sans passer par la maintenance
        await db.flush()
    await fiche_service._hand_over(db, f, data, on)  # cree l'affectation (materiel « Attribue »)
    f = await db.get(FicheDetention, fiche_id, populate_existing=True)
    if transfer:
        await notification_service.notify_former(db, f, _actor(p))
    return await _finish(db, p, f, flat, "TRANSFER" if transfer else "HAND_OVER")


# ----------------------------- affectation directe (sans circuit de demande) -----------------------------
async def transfer(db: AsyncSession, p: Principal, data: TransfertCreate) -> Affectation:
    """AFFECTATION : le depositaire comptable retire un materiel a son detenteur et l'affecte a un autre agent, en une
    seule operation : l'ancienne affectation est close, la nouvelle ouverte, un dossier de transfert est garde et
    l'ancien detenteur est prevenu. Tout est valide ensemble, ou rien."""
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
    # 3) dossier de transfert : retrouvable dans « Demandes de matériel » et dans l'historique des transferts
    fiche = await fiche_service.attach_or_create(db, nouvelle)
    fiche.type_demande, fiche.ancien_agent_id, fiche.ancienne_affectation_id = "AFFECTATION", old.agent_id, old.id
    fiche.besoin = f"Affectation directe : matériel retiré à {ancien_nom}"
    fiche.valide_par = p.user.nom_utilisateur if p.user else "Dépositaire comptable"
    await db.flush()
    await notification_service.notify_former(db, fiche, _actor(p))
    await audit_service.record(db, "TRANSFER", "affectation", nouvelle.id,
                               {"materiel_id": m.id, "de": ancien_nom, "vers": f"{nouveau.prenom} {nouveau.nom}", "fiche": fiche.reference})
    await db.commit()
    return await affectation_service.get(db, nouvelle.id)


# ----------------------------- 5 : approbation de la reception par le chef de service -----------------------------
async def approve_reception(db: AsyncSession, p: Principal, fiche_id: int) -> dict[str, Any]:
    f, flat = await _load(db, p, fiche_id, "A_APPROUVER_RECEPTION", "approuver-reception")
    f.reception_approuvee_le, f.reception_approuvee_par = _now(), _actor(p)
    return await _finish(db, p, f, flat, "APPROVE_RECEPTION")


# ----------------------------- notifications -----------------------------
async def _named(db: AsyncSession, rows: list[Notification]) -> list[dict[str, Any]]:
    agents = {a.id: f"{a.prenom} {a.nom}" for a in (await db.scalars(select(Agent).where(Agent.id.in_({n.destinataire_agent_id for n in rows} or {0})))).all()}
    return [{**{c: getattr(n, c) for c in (
        "id", "fiche_id", "evenement", "destinataire_agent_id", "canal", "adresse", "sujet", "message", "lien", "statut", "cree_le")},
        "destinataire_nom": agents.get(n.destinataire_agent_id)} for n in rows]


async def fiche_notifications(db: AsyncSession, p: Principal, fiche_id: int) -> list[dict[str, Any]]:
    """Liens a ouvrir pour prevenir la personne suivante : reserves a celui qui les a declenches (et a l'administrateur)."""
    await get_demande(db, p, fiche_id)
    stmt = select(Notification).where(Notification.fiche_id == fiche_id, Notification.canal != "APPLICATION").order_by(Notification.id.desc()).limit(40)
    rows = [n for n in (await db.scalars(stmt)).all() if p.has("notification.envoyer") or n.cree_par == _actor(p)]
    latest = max((n.evenement for n in rows[:1]), default=None)
    return await _named(db, [n for n in rows if n.evenement == latest and n.statut == "A_ENVOYER"])


async def my_notifications(db: AsyncSession, p: Principal) -> list[dict[str, Any]]:
    if p.user is None or p.agent_id is None:
        return []
    stmt = select(Notification).where(Notification.destinataire_agent_id == p.agent_id, Notification.canal == "APPLICATION").order_by(Notification.id.desc()).limit(50)
    return await _named(db, list((await db.scalars(stmt)).all()))


async def mark(db: AsyncSession, p: Principal, notif_id: int, statut: str) -> None:
    n = await db.get(Notification, notif_id)
    if n is None:
        raise NotFoundError("Notification introuvable.")
    mine = p.agent_id is not None and n.destinataire_agent_id == p.agent_id
    if not (p.open or mine or n.cree_par == _actor(p) or p.has("notification.envoyer")):
        raise ForbiddenError("Cette notification ne vous concerne pas.")
    n.statut = statut
    if statut == "ENVOYEE":
        n.envoye_le = _now()
    else:
        n.lu_le = _now()
    await db.commit()


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
