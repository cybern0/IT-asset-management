# Tracabilite des materiels : liste resumee, puis parcours chronologique d'un materiel
# (acquisition, demandes, approbation, signatures, remises, retours, receptions).
# Tout est reconstitue a partir des tables existantes : rien n'est stocke en plus.
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import NotFoundError
from crud_api.models import (
    Affectation, Agent, FicheDetention, Materiel, Service, Utilisateur,
)

# Ordre des evenements d'une MEME journee (un retour precede la remise suivante : transfert)
_RANK = {
    "ACQUISITION": 0, "ENREGISTREMENT": 1, "DEMANDE": 2, "APPROBATION": 3, "SIGNATURE_AGENT": 4, "SIGNATURE_CHEF": 4,
    "SIGNATURE": 4, "RETOUR": 5, "REMISE": 6, "AFFECTATION_DIRECTE": 6, "RECEPTION": 7, "REFUS": 8, "ANNULATION": 8,
}


def _day(v: date | datetime | None) -> date | None:
    return v.date() if isinstance(v, datetime) else v


def _agent_name(a: Agent | None, memo: str | None = None) -> str | None:
    """Nom de l'agent ; a defaut (agent supprime, parc_12.sql) le nom memorise sur la ligne."""
    return f"{a.prenom} {a.nom}".strip() if a else memo


async def summary(db: AsyncSession) -> list[dict[str, Any]]:
    """Une ligne par materiel : detenteur actuel, nombre de detenteurs successifs, dernier mouvement."""
    materiels = list((await db.scalars(select(Materiel).order_by(Materiel.code_inventaire))).all())
    stats = {
        r.materiel_id: r
        for r in (await db.execute(
            select(Affectation.materiel_id, func.count().label("n"), func.max(Affectation.date_remise).label("last_in"),
                   func.max(Affectation.date_retour).label("last_out")).group_by(Affectation.materiel_id)
        )).all()
    }
    holders = {
        a.materiel_id: (a, ag, sv)
        for a, ag, sv in (await db.execute(
            select(Affectation, Agent, Service)
            .outerjoin(Agent, Agent.id == Affectation.agent_id)
            .outerjoin(Service, Service.id == Agent.service_id)
            .where(Affectation.date_retour.is_(None))
        )).all()
    }
    out = []
    for m in materiels:
        st = stats.get(m.id)
        held = holders.get(m.id)
        last = max([d for d in (_day(m.cree_le), st and st.last_in, st and st.last_out) if d])
        out.append({
            "id": m.id, "code_inventaire": m.code_inventaire, "designation": m.designation,
            "categorie": m.categorie.libelle, "categorie_code": m.categorie.code, "statut": m.statut, "etat": m.etat,
            "marque": m.marque, "modele": m.modele, "numero_serie": m.numero_serie, "localisation": m.localisation,
            "detenteur": _agent_name(held[1], held[0].agent_nom) if held else None,
            "service": held[2].nom if held and held[2] else None,
            "depuis": held[0].date_remise if held else None,
            "nb_detenteurs": st.n if st else 0, "dernier_mouvement": last,
        })
    return out


async def detail(db: AsyncSession, materiel_id: int) -> dict[str, Any]:
    m = await db.get(Materiel, materiel_id)
    if m is None:
        raise NotFoundError("Matériel introuvable.")
    affs = list((await db.scalars(select(Affectation).where(Affectation.materiel_id == m.id))).all())
    fiches = list((await db.scalars(select(FicheDetention).where(FicheDetention.materiel_id == m.id))).all())

    agent_ids = {x for a in affs for x in (a.agent_id,)} | {x for f in fiches for x in (f.agent_id, f.ancien_agent_id)}
    agents = {a.id: a for a in (await db.scalars(select(Agent).where(Agent.id.in_(agent_ids - {None})))).all()} if agent_ids - {None} else {}
    user_ids = {u for f in fiches for u in (f.demande_par, f.approuve_par, f.signature_agent_par, f.signature_chef_par, f.reception_approuvee_par)}
    user_ids |= {a.cree_par for a in affs}
    user_ids -= {None}
    users = {u.id: u.nom_utilisateur for u in (await db.scalars(select(Utilisateur).where(Utilisateur.id.in_(user_ids)))).all()} if user_ids else {}
    who = lambda uid: users.get(uid) if uid else None  # noqa: E731
    linked = {f.affectation_id for f in fiches if f.affectation_id}
    old_holder = {a.id: a for a in affs}  # ancienne affectation -> son detenteur

    ev: list[dict[str, Any]] = []

    def add(type_: str, when: date | datetime | None, **kw: Any) -> None:
        d = _day(when)
        if d is not None:
            ev.append({"type": type_, "date": d, **kw})

    if m.date_acquisition:
        add("ACQUISITION", m.date_acquisition, provenance=m.provenance, detail=m.provenance_detail)
    add("ENREGISTREMENT", m.cree_le)

    for f in fiches:
        agent = _agent_name(agents.get(f.agent_id), f.agent_nom)
        ref, typ = f.reference, f.type_demande
        ancien = None
        if f.ancien_agent_id or f.ancienne_affectation_id:
            prev = old_holder.get(f.ancienne_affectation_id)
            ancien = _agent_name(agents.get(f.ancien_agent_id), prev.agent_nom if prev else None)
        base = {"reference": ref, "type_demande": typ, "agent": agent, "ancien_agent": ancien}
        add("DEMANDE", f.date_demande, par=who(f.demande_par), besoin=f.besoin, **base)
        if f.approuve_le:
            add("APPROBATION", f.approuve_le, par=who(f.approuve_par), **base)
        elif f.date_validation:  # dossier du circuit historique (valide_par = nom du manager)
            add("APPROBATION", f.date_validation, par=f.valide_par, **base)
        if f.signature_agent_le or f.signature_chef_le:
            add("SIGNATURE_AGENT", f.signature_agent_le, par=who(f.signature_agent_par), **base)
            add("SIGNATURE_CHEF", f.signature_chef_le, par=who(f.signature_chef_par), signe_par=f.signe_par, **base)
        elif f.statut == "SIGNEE" and f.date_signature:  # historique : une seule date pour les deux signatures
            add("SIGNATURE", f.date_signature, signe_par=f.signe_par, **base)
        add("REMISE", f.date_remise, etat=f.etat_constate, accessoires=f.accessoires, **base)
        if f.reception_approuvee_le:
            add("RECEPTION", f.reception_approuvee_le, par=who(f.reception_approuvee_par), **base)
        if f.cloture:  # aucune date de cloture n'est stockee : on place l'evenement apres le dernier du dossier
            last = max([e["date"] for e in ev if e.get("reference") == ref] or [f.date_demande])
            add("REFUS" if f.cloture == "REFUSEE" else "ANNULATION", last, motif=f.motif_refus or f.motif_cloture, **base)

    for a in affs:
        agent = _agent_name(agents.get(a.agent_id), a.agent_nom)
        if a.id not in linked:  # sans dossier : affectation directe
            add("AFFECTATION_DIRECTE", a.date_remise, agent=agent, etat=a.etat_remise, par=who(a.cree_par), observations=a.observations)
        add("RETOUR", a.date_retour, agent=agent, etat=a.etat_retour, observations=a.observations)

    ev.sort(key=lambda e: (e["date"], _RANK.get(e["type"], 9)))
    current = next((a for a in affs if a.date_retour is None), None)
    return {
        "materiel": {
            "id": m.id, "code_inventaire": m.code_inventaire, "designation": m.designation, "categorie": m.categorie.libelle,
            "marque": m.marque, "modele": m.modele, "numero_serie": m.numero_serie, "statut": m.statut, "etat": m.etat,
            "localisation": m.localisation, "date_acquisition": m.date_acquisition,
            "detenteur": _agent_name(agents.get(current.agent_id), current.agent_nom) if current else None,
            "depuis": current.date_remise if current else None,
        },
        "evenements": ev,
    }
