# Circuit de demande : demande -> approbation (depositaire comptable) -> signatures -> remise -> approbation de reception
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from crud_api.schemas.common import ORMModel, OptDate, OptS, OptText
from crud_api.schemas.fiche import AttributionOut


class DemandeCreate(BaseModel):
    """Etape 1. `agent_id` est ignore pour un agent standard : la demande est toujours faite pour lui-meme."""

    agent_id: int | None = None
    type_demande: Literal["ATTRIBUTION", "AFFECTATION"] = "ATTRIBUTION"
    categorie_id: int | None = None
    besoin: OptText = None
    canal: Literal["MAIL", "TICKET", "FORMULAIRE", "SMS", "WHATSAPP"] = "FORMULAIRE"
    reference_canal: OptS(120) = None
    demandeur: OptS(150) = None


class ApprouverIn(BaseModel):
    materiel_id: int
    date: OptDate = None


class DemandeOut(AttributionOut):
    type_demande: str
    phase: str
    role_attendu: str | None
    actions: list[str] = []  # gestes que L'UTILISATEUR CONNECTE peut faire maintenant (RBAC calcule cote API)
    chef_nom: str | None = None
    ancien_agent_id: int | None = None  # affectation : agent dont le materiel est retire
    ancien_detenteur: str | None = None
    approuve_le: datetime | None
    motif_refus: str | None
    signature_agent_le: datetime | None
    signature_chef_le: datetime | None
    reception_approuvee_le: datetime | None


class NotificationOut(ORMModel):
    id: int
    fiche_id: int | None
    evenement: str
    destinataire_agent_id: int
    destinataire_nom: str | None = None
    canal: str
    adresse: str | None
    sujet: str | None
    message: str
    lien: str | None
    statut: str
    cree_le: datetime
