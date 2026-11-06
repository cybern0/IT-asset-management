# TOUTE la logique metier et acces aux donnees des utilisateurs
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import ConflictError, UnauthorizedError, UnprocessableError
from crud_api.core.security import hash_password, verify_password
from crud_api.models import Role, Utilisateur
from crud_api.schemas.user import ProfileUpdate, UserCreate
from crud_api.services import audit_service
from crud_api.services.base import CRUDService

logger = logging.getLogger(__name__)

# Hash factice : on verifie toujours un mot de passe, meme si le compte n'existe pas
_DUMMY_HASH = hash_password("mot-de-passe-factice")


class UserService(CRUDService[Utilisateur]):
    model = Utilisateur
    label = "Utilisateur"

    async def _is_active_admin(self, db: AsyncSession, user: Utilisateur) -> bool:
        if not user.actif:
            return False
        code = await db.scalar(select(Role.code).where(Role.id == user.role_id))
        return code == "ADMIN"

    async def _ensure_other_admin(self, db: AsyncSession, user: Utilisateur) -> None:
        """Il doit toujours rester un administrateur actif."""
        if not await self._is_active_admin(db, user):
            return
        others = await db.scalar(
            select(func.count())
            .select_from(Utilisateur)
            .join(Role, Role.id == Utilisateur.role_id)
            .where(Role.code == "ADMIN", Utilisateur.actif.is_(True), Utilisateur.id != user.id)
        )
        if not others:
            raise ConflictError("Impossible : il doit rester au moins un administrateur actif.")

    async def _admin_role_id(self, db: AsyncSession) -> int:
        """Id du seul role existant : ADMIN."""
        role_id = await db.scalar(select(Role.id).where(Role.code == "ADMIN"))
        if role_id is None:
            raise UnprocessableError("Le rôle ADMIN est introuvable (exécutez parc_13.sql puis parc_14.sql).", field="role_code")
        return role_id

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        values["mot_de_passe_hash"] = hash_password(values.pop("mot_de_passe"))
        values.pop("role_code", None)
        values["role_id"] = await self._admin_role_id(db)  # tout compte est administrateur
        return values

    async def prepare_update(self, db: AsyncSession, obj: Utilisateur, values: dict[str, Any]) -> dict[str, Any]:
        password = values.pop("mot_de_passe", None)
        if password:
            values["mot_de_passe_hash"] = hash_password(password)
        values.pop("role_code", None)  # le role ne change jamais
        if values.get("actif") is False:
            await self._ensure_other_admin(db, obj)  # il doit rester un administrateur actif
        return values

    async def before_delete(self, db: AsyncSession, obj: Utilisateur) -> None:
        await self._ensure_other_admin(db, obj)

    async def authenticate(self, db: AsyncSession, nom_utilisateur: str, mot_de_passe: str) -> Utilisateur:
        user = (
            await db.scalars(select(Utilisateur).where(Utilisateur.nom_utilisateur == nom_utilisateur))
        ).first()
        valid = verify_password(mot_de_passe, user.mot_de_passe_hash if user else _DUMMY_HASH)
        if user is None or not valid or not user.actif:
            raise UnauthorizedError("Identifiants invalides.")
        user.derniere_connexion = datetime.now(UTC)
        db.info["actor_id"] = user.id
        await audit_service.record(db, "LOGIN", "utilisateur", user.id)
        await db.commit()
        return user

    async def update_profile(self, db: AsyncSession, user: Utilisateur, data: ProfileUpdate) -> Utilisateur:
        """Un utilisateur modifie son propre nom et/ou mot de passe (role, statut : jamais).

        Erreurs en 422 (et non 401) : l'interface deconnecte l'utilisateur sur tout 401."""
        if not verify_password(data.mot_de_passe_actuel, user.mot_de_passe_hash):
            raise UnprocessableError("Mot de passe actuel incorrect.", field="mot_de_passe_actuel")
        changed: list[str] = []
        if data.nom_utilisateur and data.nom_utilisateur != user.nom_utilisateur:
            user.nom_utilisateur = data.nom_utilisateur
            changed.append("nom_utilisateur")
        if data.nouveau_mot_de_passe:
            if data.nouveau_mot_de_passe == data.mot_de_passe_actuel:
                raise UnprocessableError(
                    "Le nouveau mot de passe doit être différent de l’actuel.", field="nouveau_mot_de_passe"
                )
            user.mot_de_passe_hash = hash_password(data.nouveau_mot_de_passe)
            changed.append("mot_de_passe")  # seul le nom du champ est journalise, jamais sa valeur
        if not changed:
            raise UnprocessableError("Aucune modification à enregistrer.")
        await self._flush(db, "update")  # nom deja pris -> 409 « Cette valeur existe déjà. »
        await audit_service.record(db, "UPDATE_PROFIL", "utilisateur", user.id, {"champs": changed})
        await db.commit()
        return await self.get(db, user.id)

    async def bootstrap_admin(self, db: AsyncSession, password: str) -> None:
        """Cree le compte `admin` si la table est vide (utile quand l'authentification est activee)."""
        if await db.scalar(select(func.count()).select_from(Utilisateur)):
            return
        role_id = await db.scalar(select(Role.id).where(Role.code == "ADMIN"))
        if role_id is None:
            logger.warning("Role ADMIN introuvable : compte admin non cree (voir parc.sql).")
            return
        await self.create(
            db, UserCreate(nom_utilisateur="admin", mot_de_passe=password, role_code="ADMIN")
        )
        logger.info("Compte `admin` cree.")


user_service = UserService()
