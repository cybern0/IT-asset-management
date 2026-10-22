# Dependances FastAPI : utilisateur courant (authentification optionnelle)
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import get_settings
from crud_api.core.database import get_db
from crud_api.core.errors import UnauthorizedError
from crud_api.core.security import decode_access_token
from crud_api.models import Utilisateur

bearer_scheme = HTTPBearer(auto_error=False)


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
