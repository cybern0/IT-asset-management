from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from crud_api.schemas.common import (
    CATEGORY_MENU, ETAT, PROVENANCE, STATUT, ORMModel, OptDate, OptS, OptText, S, partial,
)


class CategorieCreate(BaseModel):
    code: S(30)
    libelle: S(100)
    category_menu: CATEGORY_MENU = "Matériel"  # menu de l'interface sous lequel l'onglet de la categorie apparait


CategorieUpdate = partial(CategorieCreate, "CategorieUpdate")


class CategorieOut(ORMModel):
    id: int
    code: str
    libelle: str
    category_menu: str


class MaterielCreate(BaseModel):
    code_inventaire: S(60)
    categorie_id: int
    designation: S(180)
    marque: OptS(100) = None
    modele: OptS(100) = None
    numero_serie: OptS(150) = None
    caracteristiques: OptText = None  # « cle: valeur, cle: valeur »
    provenance: PROVENANCE = "ACHAT"
    provenance_detail: OptS(180) = None
    date_acquisition: OptDate = None
    valeur_acquisition: Annotated[Decimal | None, Field(ge=0, max_digits=14, decimal_places=2)] = None
    etat: ETAT = "BON"
    statut: STATUT = "EN_STOCK"
    localisation: OptS(180) = None
    observations: OptText = None


MaterielUpdate = partial(MaterielCreate, "MaterielUpdate")


class MaterielOut(ORMModel):
    id: int
    code_inventaire: str
    categorie_id: int
    categorie_code: str
    designation: str
    marque: str | None
    modele: str | None
    numero_serie: str | None
    caracteristiques: str | None
    provenance: str
    provenance_detail: str | None
    date_acquisition: date | None
    valeur_acquisition: Decimal | None
    etat: str
    statut: str
    localisation: str | None
    observations: str | None
    cree_le: datetime
    a_image: bool = False


class AffectationCreate(BaseModel):
    materiel_id: int
    agent_id: int
    date_remise: OptDate = None  # defaut : aujourd'hui
    date_retour: OptDate = None
    etat_remise: ETAT | None = None
    etat_retour: ETAT | None = None
    observations: OptText = None
    cree_par: int | None = None  # defaut : utilisateur connecte


AffectationUpdate = partial(AffectationCreate, "AffectationUpdate")


class AffectationOut(ORMModel):
    id: int
    materiel_id: int
    agent_id: int | None  # None : agent supprime de la base (voir agent_nom)
    agent_matricule: str | None = None
    agent_nom: str | None = None
    date_remise: date
    date_retour: date | None
    etat_remise: str | None
    etat_retour: str | None
    observations: str | None
    cree_par: int | None
    cree_le: datetime
