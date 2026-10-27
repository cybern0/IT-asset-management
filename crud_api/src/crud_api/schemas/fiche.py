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


class MotifIn(BaseModel):
    motif: OptText = None


class SignatureIn(BaseModel):
    """Etat de signature de la fiche, fixe a la main par l'administrateur (la signature elle-meme a lieu hors de
    l'application). `signee=False` remet la fiche « a signer » et efface les informations de signature."""

    signee: bool
    date: OptDate = None  # date de signature ; defaut : aujourd'hui
    mode_signature: Literal["MANUSCRITE", "ELECTRONIQUE"] | None = None  # defaut : manuscrite
    signe_par: OptS(150) = None


class AvancerIn(BaseModel):
    """Etape suivante du dossier. La signature, la validation et la remise se font hors de l'application :
    on se contente d'enregistrer qu'elles ont eu lieu. Seules les informations de l'etape en cours sont lues,
    toutes sont facultatives sauf celles que l'etape exige (voir fiche_service.advance)."""

    date: OptDate = None  # date de l'etape (validation, signature ou remise) ; defaut : aujourd'hui
    valide_par: OptS(150) = None  # etape 1 : manager qui a valide
    materiel_id: int | None = None  # etape 2 : equipement choisi en stock
    mode_signature: Literal["MANUSCRITE", "ELECTRONIQUE"] | None = None  # etape 4 (defaut : manuscrite)
    signe_par: OptS(150) = None  # etape 4 : responsable signataire
    etat_constate: Literal["NEUF", "BON", "A_REPARER"] | None = None  # etape 5 : controle visuel
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
    signature_modifiee_par: str | None
    signature_modifiee_le: datetime | None
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
    materiel_provenance: str | None
    materiel_provenance_detail: str | None
    materiel_date_acquisition: date | None
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
