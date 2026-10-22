from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from crud_api.schemas.common import PROVENANCE, TYPE_MOUVEMENT, ORMModel, OptS, Qty, S, partial


class ArticleCreate(BaseModel):
    reference: S(60)
    designation: S(180)
    categorie: OptS(100) = None
    unite: S(30) = "unite"
    seuil_alerte: Qty = Decimal(0)
    actif: bool = True


ArticleUpdate = partial(ArticleCreate, "ArticleUpdate")


class ArticleOut(ORMModel):
    id: int
    reference: str
    designation: str
    categorie: str | None
    unite: str
    seuil_alerte: Decimal
    actif: bool


class StockCreate(BaseModel):
    article_id: int
    service_id: int | None = None  # None = stock central
    quantite: Qty = Decimal(0)


StockUpdate = partial(StockCreate, "StockUpdate")


class StockOut(ORMModel):
    id: int
    article_id: int
    service_id: int | None
    quantite: Decimal


class MouvementCreate(BaseModel):
    article_id: int
    service_source_id: int | None = None
    service_destination_id: int | None = None
    type_mouvement: TYPE_MOUVEMENT
    quantite: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
    reference_document: OptS(100) = None
    provenance: PROVENANCE | None = None
    motif: S(2000)
    effectue_par: int | None = None  # defaut : utilisateur connecte


class MouvementOut(ORMModel):
    id: int
    article_id: int
    service_source_id: int | None
    service_destination_id: int | None
    type_mouvement: str
    quantite: Decimal
    reference_document: str | None
    provenance: str | None
    motif: str
    effectue_par: int
    cree_le: datetime
