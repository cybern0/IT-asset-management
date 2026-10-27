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
from crud_api.models import Role, Utilisateur

bearer_scheme = HTTPBearer(auto_error=False)

# Codes de la table `role` (parc_4.sql). LECTURE = utilisateur « standard », en lecture seule.
ADMIN = "ADMIN"
GESTIONNAIRE = "GESTIONNAIRE"
LECTURE = "LECTURE"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Utilisateur | None:
    """Si AUTH_ENABLED=false (defaut), l'API est ouverte et renvoie None.
    Sinon exige un jeton Bearer valide et memorise l'auteur pour le journal d'audit."""
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
