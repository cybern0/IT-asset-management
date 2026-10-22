# Types partages et utilitaires des schemas Pydantic
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, create_model

ETAT = Literal["NEUF", "BON", "A_REPARER", "EN_PANNE", "REFORME"]
STATUT = Literal["EN_STOCK", "ATTRIBUE", "EN_MAINTENANCE", "REFORME"]
PROVENANCE = Literal["ACHAT", "DOTATION", "AFFECTATION", "PROJET", "DON", "AUTRE"]
TYPE_LICENCE = Literal["SANS_LICENCE", "PERPETUELLE", "ABONNEMENT"]
TYPE_MOUVEMENT = Literal["ENTREE", "SORTIE", "TRANSFERT", "AJUSTEMENT"]


def _blank_to_none(value):
    """Une chaine vide devient NULL (evite les doublons '' sur les colonnes UNIQUE)."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def S(max_length: int):
    """Chaine obligatoire, sans espaces autour."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


def OptS(max_length: int):
    """Chaine facultative : vide -> None (la contrainte ne vise que la branche str)."""
    return Annotated[S(max_length) | None, BeforeValidator(_blank_to_none)]


OptText = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptDate = Annotated[date | None, BeforeValidator(_blank_to_none)]
Qty = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


class ORMModel(BaseModel):
    """Schema de sortie : lu depuis un objet SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


def partial(model: type[BaseModel], name: str) -> type[BaseModel]:
    """Version « tous les champs facultatifs » d'un schema de creation (pour PATCH)."""
    fields = {}
    for field_name, info in model.model_fields.items():
        annotation = info.annotation | None
        if info.metadata:
            annotation = Annotated[(annotation, *info.metadata)]
        fields[field_name] = (annotation, None)
    return create_model(name, **fields)
