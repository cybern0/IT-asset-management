from datetime import date, datetime

from pydantic import BaseModel, Field

from crud_api.schemas.common import TYPE_LICENCE, ORMModel, OptDate, OptS, OptText, S, partial


class LogicielCreate(BaseModel):
    nom: S(180)
    editeur: OptS(150) = None
    version: OptS(60) = None
    type_licence: TYPE_LICENCE = "PERPETUELLE"
    observations: OptText = None


LogicielUpdate = partial(LogicielCreate, "LogicielUpdate")


class LogicielOut(ORMModel):
    id: int
    nom: str
    editeur: str | None
    version: str | None
    type_licence: str
    observations: str | None
    cree_le: datetime


class LicenceCreate(BaseModel):
    logiciel_id: int
    cle_licence: OptS(255) = None
    nombre_postes: int = Field(default=1, gt=0)
    date_expiration: OptDate = None
    observations: OptText = None


LicenceUpdate = partial(LicenceCreate, "LicenceUpdate")


class LicenceOut(ORMModel):
    id: int
    logiciel_id: int
    cle_licence: str | None
    nombre_postes: int
    date_expiration: date | None
    observations: str | None
    cree_le: datetime
