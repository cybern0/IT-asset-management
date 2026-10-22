from crud_api.schemas.common import ORMModel, BaseModel, OptS, S, partial
from pydantic import EmailStr, BeforeValidator
from typing import Annotated
from crud_api.schemas.common import _blank_to_none


class DirectionCreate(BaseModel):
    code: S(30)
    nom: S(180)
    actif: bool = True


DirectionUpdate = partial(DirectionCreate, "DirectionUpdate")


class DirectionOut(ORMModel):
    id: int
    code: str
    nom: str
    actif: bool


class ServiceCreate(BaseModel):
    direction_id: int
    code: S(30)
    nom: S(180)
    site: OptS(150) = None
    actif: bool = True


ServiceUpdate = partial(ServiceCreate, "ServiceUpdate")


class ServiceOut(ORMModel):
    id: int
    direction_id: int
    code: str
    nom: str
    site: str | None
    actif: bool


class AgentCreate(BaseModel):
    matricule: S(50)
    nom: S(100)
    prenom: S(100)
    fonction: OptS(150) = None
    email: Annotated[EmailStr | None, BeforeValidator(_blank_to_none)] = None
    service_id: int | None = None
    actif: bool = True


AgentUpdate = partial(AgentCreate, "AgentUpdate")


class AgentOut(ORMModel):
    id: int
    matricule: str
    nom: str
    prenom: str
    fonction: str | None
    email: str | None
    service_id: int | None
    actif: bool
