# Notifications sans serveur : le backend fabrique des liens mailto:, sms: et https://wa.me/ que l'appareil de la
# personne ouvre (messagerie, application SMS, WhatsApp). Aucun serveur SMTP ni passerelle SMS n'est necessaire.
import re
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.models import Agent, FicheDetention, Notification, Role, Utilisateur

# phase atteinte -> (evenement, qui prevenir, sujet, texte)
STEPS = {
    "A_APPROUVER": ("DEMANDE_CREEE", "admin", "Nouvelle demande {ref}",
                    "{agent} {demande}. Merci de l'approuver et de mettre la base à jour."),
    "A_SIGNER_AGENT": ("SIGNATURE_AGENT_REQUISE", "agent", "Demande {ref} approuvée : votre signature",
                       "Votre demande {ref} est approuvée. Merci de signer la fiche auprès du dépositaire comptable."),
    "A_SIGNER_CHEF": ("SIGNATURE_CHEF_REQUISE", "chef", "Fiche {ref} : signature du chef de service",
                      "{agent} a signé la fiche {ref}. Merci de la signer à votre tour auprès du dépositaire comptable."),
    "A_REMETTRE": ("DEMANDE_APPROUVEE", "admin", "Fiche {ref} signée : remise du matériel",
                   "La fiche {ref} est signée par l'agent et son chef de service. Le matériel peut être remis."),
    "A_APPROUVER_RECEPTION": ("RECEPTION_A_APPROUVER", "chef", "Matériel remis ({ref}) : approuvez la réception",
                              "Le matériel de {agent} a été remis (fiche {ref}). Merci de confirmer la réception auprès du dépositaire comptable."),
    "TERMINEE": ("DOSSIER_TERMINE", "agent", "Dossier {ref} terminé", "La réception de votre matériel est approuvée ({ref})."),
    "CLOTUREE": ("DEMANDE_REFUSEE", "agent", "Demande {ref} refusée", "Votre demande {ref} n'a pas été retenue. {motif}"),
}


def phone_digits(number: str | None) -> str | None:
    """Chiffres du numero au format international (0xx -> indicatif du pays)."""
    d = re.sub(r"\D", "", number or "")
    if d.startswith("00"):
        d = d[2:]
    elif d.startswith("0"):
        d = get_settings().country_code + d[1:]
    return d or None


def mail_link(addr: str, subject: str, body: str) -> str:
    return f"mailto:{quote(addr, safe='@')}?subject={quote(subject, safe='')}&body={quote(body, safe='')}"


def sms_link(digits: str, body: str) -> str:
    return f"sms:+{digits}?body={quote(body, safe='')}"


def whatsapp_link(digits: str, body: str) -> str:
    return f"https://wa.me/{digits}?text={quote(body, safe='')}"


async def _admins(db: AsyncSession) -> list[tuple[Agent, Utilisateur]]:
    rows = await db.execute(
        select(Agent, Utilisateur).join(Utilisateur, Utilisateur.agent_id == Agent.id)
        .join(Role, Role.id == Utilisateur.role_id).where(Role.code == "ADMIN", Utilisateur.actif.is_(True), Agent.actif.is_(True))
    )
    return [(a, u) for a, u in rows.all()]


async def _with_user(db: AsyncSession, agent_id: int | None) -> list[tuple[Agent, Utilisateur | None]]:
    agent = await db.get(Agent, agent_id) if agent_id else None
    if agent is None:
        return []
    user = await db.scalar(select(Utilisateur).where(Utilisateur.agent_id == agent.id, Utilisateur.actif.is_(True)))
    return [(agent, user)]


async def notify(db: AsyncSession, fiche: FicheDetention, phase: str, chef_agent_id: int | None, actor_id: int | None) -> list[Notification]:
    """Cree les notifications de la phase atteinte (sans commit) : message dans l'application + un lien par moyen de
    contact connu (mail, SMS, WhatsApp) pour chaque destinataire."""
    event, who, subject, text = STEPS[phase]
    if who == "admin":
        targets = await _admins(db)
    elif who == "chef":
        targets = await _with_user(db, chef_agent_id)
    else:
        targets = await _with_user(db, fiche.agent_id)
    demandeur = await db.get(Agent, fiche.agent_id)
    base = get_settings().app_url.rstrip("/")
    fmt = {
        "ref": fiche.reference, "type": fiche.type_demande.lower(),
        "demande": ("demande la réaffectation d'un matériel déjà détenu par un autre agent" if fiche.type_demande == "AFFECTATION"
                    else "demande un matériel non affecté (attribution)"), "motif": fiche.motif_refus or "",
        "agent": f"{demandeur.prenom} {demandeur.nom}" if demandeur else "",
    }
    subject, body = subject.format(**fmt), text.format(**fmt).strip()
    if base:
        body += f"\n{base}/demandes?ref={quote(fiche.reference)}"
    out: list[Notification] = []

    def add(agent: Agent, user: Utilisateur | None, canal: str, adresse: str | None, lien: str | None) -> None:
        n = Notification(
            fiche_id=fiche.id, evenement=event, destinataire_agent_id=agent.id,
            destinataire_utilisateur_id=user.id if user else None, canal=canal, adresse=adresse,
            sujet=subject, message=body, lien=lien, cree_par=actor_id,
        )
        db.add(n)
        out.append(n)

    for agent, user in targets:
        add(agent, user, "APPLICATION", None, None)
        if agent.email:
            add(agent, user, "MAIL", agent.email, mail_link(agent.email, subject, body))
        if (d := phone_digits(agent.telephone)):
            add(agent, user, "SMS", agent.telephone, sms_link(d, body))
        if (d := phone_digits(agent.whatsapp)):
            add(agent, user, "WHATSAPP", agent.whatsapp, whatsapp_link(d, body))
    await db.flush()
    return out


async def notify_former(db: AsyncSession, fiche: FicheDetention, actor_id: int | None) -> list[Notification]:
    """Affectation : prevenir l'ancien detenteur que le materiel lui est retire (sans commit)."""
    from crud_api.models import Materiel

    targets = await _with_user(db, fiche.ancien_agent_id)
    nouveau = await db.get(Agent, fiche.agent_id)
    materiel = await db.get(Materiel, fiche.materiel_id) if fiche.materiel_id else None
    subject = f"Matériel retiré ({fiche.reference})"
    body = (f"Le matériel {materiel.code_inventaire if materiel else ''} vous a été retiré et affecté à "
            f"{nouveau.prenom + ' ' + nouveau.nom if nouveau else 'un autre agent'} (fiche {fiche.reference}).")
    out: list[Notification] = []
    for agent, user in targets:
        rows = [("APPLICATION", None, None)]
        if agent.email:
            rows.append(("MAIL", agent.email, mail_link(agent.email, subject, body)))
        if (d := phone_digits(agent.telephone)):
            rows.append(("SMS", agent.telephone, sms_link(d, body)))
        if (d := phone_digits(agent.whatsapp)):
            rows.append(("WHATSAPP", agent.whatsapp, whatsapp_link(d, body)))
        for canal, adresse, lien in rows:
            n = Notification(
                fiche_id=fiche.id, evenement="MATERIEL_RETIRE", destinataire_agent_id=agent.id,
                destinataire_utilisateur_id=user.id if user else None, canal=canal, adresse=adresse,
                sujet=subject, message=body, lien=lien, cree_par=actor_id,
            )
            db.add(n)
            out.append(n)
    await db.flush()
    return out
