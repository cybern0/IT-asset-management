# Utilisateurs, roles, permissions
from datetime import datetime

from pydantic import BaseModel, Field

from crud_api.schemas.common import ORMModel, S, partial


class PermissionCreate(BaseModel):
    code: S(80)
    libelle: S(180)


PermissionUpdate = partial(PermissionCreate, "PermissionUpdate")


class PermissionOut(ORMModel):
    id: int
    code: str
    libelle: str


class RoleCreate(BaseModel):
    code: S(30)
    libelle: S(100)
    permission_ids: list[int] = Field(default_factory=list)  # table role_permission


RoleUpdate = partial(RoleCreate, "RoleUpdate")


class RoleOut(ORMModel):
    id: int
    code: str
    libelle: str
    permission_ids: list[int]


class UserCreate(BaseModel):
    agent_id: int | None = None
    nom_utilisateur: S(80)
    mot_de_passe: str = Field(min_length=8, max_length=128)
    role_id: int
    actif: bool = True


UserUpdate = partial(UserCreate, "UserUpdate")


class UserOut(ORMModel):
    """Le hash du mot de passe n'est jamais renvoye."""

    id: int
    agent_id: int | None
    nom_utilisateur: str
    role_id: int
    actif: bool
    derniere_connexion: datetime | None
    cree_le: datetime
    role_code: str | None = None  # renseigne par /auth/login et /auth/me (ADMIN, GESTIONNAIRE, LECTURE)
    permissions: list[str] = Field(default_factory=list)  # codes de permission du role (RBAC), pour adapter l'interface


class LoginIn(BaseModel):
    nom_utilisateur: str
    mot_de_passe: str


class ProfileUpdate(BaseModel):
    """Modification de son propre compte : le mot de passe actuel est toujours exige."""

    mot_de_passe_actuel: str = Field(min_length=1, max_length=128)
    nom_utilisateur: S(80) | None = None
    nouveau_mot_de_passe: str | None = Field(default=None, min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
