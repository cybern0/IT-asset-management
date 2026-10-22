# Logiciels et licences (un logiciel « sans licence » n'accepte aucune licence)
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import ConflictError, UnprocessableError
from crud_api.models import Licence, Logiciel
from crud_api.services.base import CRUDService


class LogicielService(CRUDService[Logiciel]):
    model = Logiciel
    label = "Logiciel"

    async def _ensure_unique(
        self, db: AsyncSession, nom: str, version: str | None, exclude_id: int | None = None
    ) -> None:
        stmt = select(Logiciel.id).where(
            func.lower(Logiciel.nom) == nom.lower(), Logiciel.version.is_not_distinct_from(version)
        )
        if exclude_id is not None:
            stmt = stmt.where(Logiciel.id != exclude_id)
        if (await db.scalar(stmt.limit(1))) is not None:
            raise ConflictError("Ce logiciel existe déjà avec cette version.", field="nom")

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_unique(db, values["nom"], values.get("version"))
        return values

    async def prepare_update(self, db: AsyncSession, obj: Logiciel, values: dict[str, Any]) -> dict[str, Any]:
        if "nom" in values or "version" in values:
            await self._ensure_unique(
                db, values.get("nom", obj.nom), values.get("version", obj.version), exclude_id=obj.id
            )
        if values.get("type_licence") == "SANS_LICENCE" and obj.type_licence != "SANS_LICENCE":
            count = await db.scalar(
                select(func.count()).select_from(Licence).where(Licence.logiciel_id == obj.id)
            )
            if count:
                raise ConflictError(
                    "Ce logiciel a déjà des licences : supprimez-les avant de le déclarer sans licence.",
                    field="type_licence",
                )
        return values


class LicenceService(CRUDService[Licence]):
    model = Licence
    label = "Licence"

    async def _check_logiciel(self, db: AsyncSession, logiciel_id: int) -> None:
        logiciel = await db.get(Logiciel, logiciel_id)
        if logiciel is None:
            raise UnprocessableError("Logiciel introuvable.", field="logiciel_id")
        if logiciel.type_licence == "SANS_LICENCE":
            raise ConflictError(
                "Ce logiciel est sans licence : aucune licence à enregistrer.", field="logiciel_id"
            )

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        await self._check_logiciel(db, values["logiciel_id"])
        return values

    async def prepare_update(self, db: AsyncSession, obj: Licence, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("logiciel_id") not in (None, obj.logiciel_id):
            await self._check_logiciel(db, values["logiciel_id"])
        return values


logiciel_service = LogicielService()
licence_service = LicenceService()
