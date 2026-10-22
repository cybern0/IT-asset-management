from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import get_db
from crud_api.core.deps import get_current_user
from crud_api.core.errors import UnauthorizedError
from crud_api.core.security import create_access_token
from crud_api.models import Utilisateur
from crud_api.schemas.user import LoginIn, TokenOut, UserOut
from crud_api.services.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await user_service.authenticate(db, data.nom_utilisateur, data.mot_de_passe)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: Utilisateur | None = Depends(get_current_user)):
    if user is None:
        raise UnauthorizedError("Authentification désactivée ou non connecté.")
    return user
