# Dependances FastAPI : utilisateur courant (authentification optionnelle)
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.database import get_db
from crud_api.core.errors import ForbiddenError, UnauthorizedError
from crud_api.core.security import decode_access_token
from crud_api.models import Permission, Role, Utilisateur, role_permission

bearer_scheme = HTTPBearer(auto_error=False)

# Un seul role existe dans la table `role` : ADMIN (parc_13.sql et parc_14.sql retirent les autres).
# Les DROITS ne sont pas codes ici : ils viennent des tables permission / role_permission (ADMIN les a tous).
ADMIN = "ADMIN"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Utilisateur | None:
    """Si AUTH_ENABLED=false (defaut), l'API est ouverte et renvoie None.
    Sinon exige un jeton Bearer valide et memorise l'auteur (db.info["actor_id"])."""
    if not get_settings().auth_enabled:
        return None
    if credentials is None:
        raise UnauthorizedError("Authentification requise.")
    try:
        user_id = int(decode_access_token(credentials.credentials)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Jeton invalide ou expiré.") from exc
    user = await db.get(Utilisateur, user_id)
    if user is None or not user.actif:
        raise UnauthorizedError("Compte inconnu ou désactivé.")
    db.info["actor_id"] = user.id
    return user


async def require_admin(
    user: Utilisateur | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Utilisateur | None:
    """Reserve l'action au role ADMIN. Comme le reste de l'API, elle est ouverte tant que AUTH_ENABLED=false."""
    if user is not None:
        role = await db.get(Role, user.role_id)
        if role is None or role.code != "ADMIN":
            raise ForbiddenError("Seul un administrateur peut effectuer cette action.")
    return user


async def role_code_of(db: AsyncSession, user: Utilisateur) -> str | None:
    return await db.scalar(select(Role.code).where(Role.id == user.role_id))


def require_roles(*, read: frozenset[str], write: frozenset[str], delete: frozenset[str] | None = None):
    """Autorisation par role selon la methode HTTP : lecture (GET), ecriture (POST/PATCH...) et suppression (DELETE).

    `delete` vaut `write` s'il est omis. Ouvert tant que AUTH_ENABLED=false, comme le reste de l'API.
    L'authentification (401) est verifiee avant, par get_current_user ; un role insuffisant donne 403.
    """
    delete_roles = write if delete is None else delete

    async def checker(
        request: Request,
        user: Utilisateur | None = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        if user is None:
            return
        if request.method in SAFE_METHODS:
            allowed = read
        elif request.method == "DELETE":
            allowed = delete_roles
        else:
            allowed = write
        if await role_code_of(db, user) not in allowed:
            raise ForbiddenError("Votre rôle ne permet pas d'effectuer cette action.")

    return checker


# ----------------------------- RBAC modulaire : droits lus en base (permission / role_permission) -----------------------------
async def permissions_of(db: AsyncSession, user: Utilisateur) -> frozenset[str]:
    """Codes de permission du role de l'utilisateur. Changer les droits d'un role = modifier role_permission."""
    rows = await db.scalars(
        select(Permission.code)
        .join(role_permission, role_permission.c.permission_id == Permission.id)
        .where(role_permission.c.role_id == user.role_id)
    )
    return frozenset(rows.all())


class Principal:
    """Utilisateur connecte et ses permissions. `user` vaut None quand AUTH_ENABLED=false : tout est alors permis."""

    def __init__(self, user: Utilisateur | None, perms: frozenset[str]):
        self.user = user
        self.perms = perms

    @property
    def open(self) -> bool:
        return self.user is None

    @property
    def agent_id(self) -> int | None:
        return self.user.agent_id if self.user else None

    def has(self, code: str) -> bool:
        return self.open or code in self.perms

    def has_any(self, *codes: str) -> bool:
        return self.open or any(c in self.perms for c in codes)


async def get_principal(
    user: Utilisateur | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Principal:
    if user is None:
        return Principal(None, frozenset())
    return Principal(user, await permissions_of(db, user))


def requires(*codes: str):
    """Dependance : exige AU MOINS UNE des permissions donnees (403 sinon) et renvoie le Principal."""

    async def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_any(*codes):
            raise ForbiddenError("Votre rôle ne permet pas d'effectuer cette action.")
        return principal

    return checker


def require_perms(*, read: frozenset[str], write: frozenset[str], delete: frozenset[str] | None = None):
    """Comme require_roles, mais par permissions : lecture (GET), ecriture (POST/PATCH...), suppression (DELETE).
    Chaque ensemble liste les permissions dont UNE SEULE suffit. `delete` vaut `write` s'il est omis."""
    delete_perms = write if delete is None else delete

    async def checker(request: Request, principal: Principal = Depends(get_principal)) -> None:
        if request.method in SAFE_METHODS:
            allowed = read
        elif request.method == "DELETE":
            allowed = delete_perms
        else:
            allowed = write
        if not principal.has_any(*allowed):
            raise ForbiddenError("Votre rôle ne permet pas d'effectuer cette action.")

    return checker
