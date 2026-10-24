from datetime import date, datetime

from crud_api.schemas.common import ORMModel


class DetentionOut(ORMModel):
    """Vue croisee : fiche + affectation + materiel + agent (une ligne par fiche)."""

    id: int
    reference: str
    statut: str  # NON_SIGNEE | SIGNEE
    date_signature: date | None
    a_fichier_signe: bool
    cree_le: datetime

    affectation_id: int
    date_remise: date
    date_retour: date | None
    en_cours: bool
    etat_remise: str | None
    etat_retour: str | None
    observations: str | None
    saisi_par: str | None

    materiel_id: int
    materiel_code: str
    materiel_designation: str
    materiel_categorie_code: str
    materiel_categorie: str
    materiel_marque: str | None
    materiel_modele: str | None
    materiel_serie: str | None
    materiel_caracteristiques: str | None
    materiel_etat: str
    materiel_statut: str
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
