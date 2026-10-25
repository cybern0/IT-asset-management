from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from crud_api.schemas.common import ORMModel, OptDate, OptS, OptText, S

CANAL = Literal["MAIL", "TICKET", "FORMULAIRE"]
ACCESSOIRES = ("Chargeur", "Sacoche", "Docking", "Souris", "Clavier")


class AttributionCreate(BaseModel):
    """Etape 1 : demande d'equipement."""

    agent_id: int
    categorie_id: int | None = None
    besoin: OptText = None
    canal: CANAL = "FORMULAIRE"
    reference_canal: OptS(120) = None
    demandeur: OptS(150) = None
    date_demande: OptDate = None  # defaut : aujourd'hui
    valide_par: OptS(150) = None  # renseigne si le manager a deja valide


class ValidationIn(BaseModel):
    valide_par: S(150)
    date_validation: OptDate = None


class MotifIn(BaseModel):
    motif: OptText = None


class SelectionIn(BaseModel):
    materiel_id: int


class RemiseIn(BaseModel):
    date_remise: OptDate = None
    etat_constate: Literal["NEUF", "BON", "A_REPARER"] | None = None
    accessoires: list[Literal["Chargeur", "Sacoche", "Docking", "Souris", "Clavier"]] = []
    accessoires_autre: OptS(100) = None
    observations: OptText = None


class AttributionOut(ORMModel):
    """Dossier d'attribution a plat : demande + materiel + agent + affectation."""

    id: int
    reference: str
    etape: int  # etape en cours (1 a 6 ; 6 = termine)
    etat: str  # EN_COURS | ATTRIBUEE | RENDUE | REFUSEE | ANNULEE
    cree_le: datetime

    # etape 1
    categorie_id: int | None
    categorie_demandee: str | None
    besoin: str | None
    canal: str
    reference_canal: str | None
    demandeur: str | None
    date_demande: date
    valide_par: str | None
    date_validation: date | None
    # etapes 2-3
    date_generation: date | None
    # etape 4
    statut: str  # NON_SIGNEE | SIGNEE
    date_signature: date | None
    mode_signature: str | None
    signe_par: str | None
    a_fichier_signe: bool
    # etape 5
    date_remise: date | None
    etat_constate: str | None
    accessoires: list[str]
    accessoires_autre: str | None
    observations_remise: str | None
    # etape 6 et suite
    affectation_id: int | None
    date_retour: date | None
    etat_retour: str | None
    observations: str | None  # observations de l'affectation (zone de restitution)
    saisi_par: str | None
    cloture: str | None
    motif_cloture: str | None

    materiel_id: int | None
    materiel_code: str | None
    materiel_designation: str | None
    materiel_categorie_code: str | None
    materiel_categorie: str | None
    materiel_marque: str | None
    materiel_modele: str | None
    materiel_serie: str | None
    materiel_caracteristiques: str | None
    materiel_etat: str | None
    materiel_statut: str | None
    materiel_localisation: str | None
    materiel_a_image: bool

    agent_id: int
    agent_matricule: str
    agent_nom: str
    agent_prenom: str
    agent_fonction: str | None
    agent_email: str | None
    service_nom: str | None
    service_site: str | None
    direction_nom: str | None
