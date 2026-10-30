from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.core.deps import get_current_user, permissions_of, role_code_of
from crud_api.core.errors import UnauthorizedError
from crud_api.core.security import create_access_token
from crud_api.models import Utilisateur
from crud_api.schemas.user import LoginIn, ProfileUpdate, TokenOut, UserOut
from crud_api.services.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Authentification"])


async def _user_out(db: AsyncSession, user: Utilisateur) -> UserOut:
    """L'interface a besoin du code du role pour adapter le menu et les boutons."""
    perms = sorted(await permissions_of(db, user))
    return UserOut.model_validate(user).model_copy(update={"role_code": await role_code_of(db, user), "permissions": perms})


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await user_service.authenticate(db, data.nom_utilisateur, data.mot_de_passe)
    return TokenOut(access_token=create_access_token(user.id), user=await _user_out(db, user))


@router.get("/me", response_model=UserOut)
async def me(user: Utilisateur | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user is None:
        raise UnauthorizedError("Authentification désactivée ou non connecté.")
    return await _user_out(db, user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: ProfileUpdate, user: Utilisateur | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Profil : l'utilisateur connecte change son nom d'utilisateur et/ou son mot de passe."""
    if user is None:
        raise UnauthorizedError("Authentification désactivée ou non connecté.")
    return await _user_out(db, await user_service.update_profile(db, user, data))
