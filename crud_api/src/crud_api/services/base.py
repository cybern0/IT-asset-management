# Socle commun des services : CRUD generique, audit, traduction des erreurs PostgreSQL
from __future__ import annotations

import re
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.database import Base
from crud_api.core.errors import ConflictError, NotFoundError, UnprocessableError
from crud_api.services import audit_service

ModelT = TypeVar("ModelT", bound=Base)

_SECRET = "mot_de_passe"


def translate_integrity_error(exc: IntegrityError, operation: str) -> Exception:
    """Convertit une erreur de contrainte PostgreSQL en erreur metier lisible."""
    orig = exc.orig
    cause = getattr(orig, "__cause__", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(cause, "sqlstate", None)
    detail = getattr(cause, "detail", None) or getattr(orig, "detail", None) or ""
    column = getattr(cause, "column_name", None) or getattr(orig, "column_name", None)

    key = re.search(r"Key \(([^)]+)\)=", detail)
    columns = [c.strip() for c in key.group(1).split(",")] if key else []
    field = columns[0] if columns else None

    if sqlstate == "23505":  # unique
        message = "Cette combinaison existe déjà." if len(columns) > 1 else "Cette valeur existe déjà."
        return ConflictError(message, field=field)
    if sqlstate == "23503":  # cle etrangere
        if operation == "delete":
            table = re.search(r'referenced from table "([^"]+)"', detail)
            where = f" (utilisé dans « {table.group(1)} »)" if table else ""
            return ConflictError(f"Suppression impossible : cet élément est utilisé ailleurs{where}.")
        return UnprocessableError("Référence introuvable.", field=field)
    if sqlstate == "23514":  # check
        return UnprocessableError("Valeur refusée par une contrainte de la base de données.")
    if sqlstate == "23502":  # not null
        return UnprocessableError("Ce champ est obligatoire.", field=column)
    return exc


class CRUDService(Generic[ModelT]):
    """CRUD generique. Les regles metier se branchent via les hooks `prepare_*` et `before_delete`."""

    model: type[ModelT]
    label: str = "Élément"

    # ----- hooks -------------------------------------------------------------
    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        return values

    async def prepare_update(self, db: AsyncSession, obj: ModelT, values: dict[str, Any]) -> dict[str, Any]:
        return values

    async def after_create(self, db: AsyncSession, obj: ModelT) -> None:
        """Appele apres l'insertion (id connu), dans la meme transaction."""
        return None

    async def before_delete(self, db: AsyncSession, obj: ModelT) -> None:
        return None

    # ----- lecture -----------------------------------------------------------
    async def list(self, db: AsyncSession, *, limit: int = 1000, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).order_by(self.model.id).limit(limit).offset(offset)  # type: ignore[attr-defined]
        return list((await db.scalars(stmt)).unique().all())

    async def get(self, db: AsyncSession, item_id: int) -> ModelT:
        stmt = (
            select(self.model)
            .where(self.model.id == item_id)  # type: ignore[attr-defined]
            .execution_options(populate_existing=True)
        )
        obj = (await db.scalars(stmt)).unique().first()
        if obj is None:
            raise NotFoundError(f"{self.label} introuvable.")
        return obj

    # ----- ecriture ----------------------------------------------------------
    async def create(self, db: AsyncSession, data: BaseModel) -> ModelT:
        values = await self.prepare_create(db, data.model_dump())
        obj = self.model(**values)
        db.add(obj)
        await self._flush(db, "insert")
        await self.after_create(db, obj)
        await self._audit(db, "CREATE", obj, sorted(data.model_fields_set))
        await db.commit()
        return await self.get(db, obj.id)  # type: ignore[attr-defined]

    async def update(self, db: AsyncSession, item_id: int, data: BaseModel) -> ModelT:
        obj = await self.get(db, item_id)
        values = data.model_dump(exclude_unset=True)
        self._reject_null_on_required(values)
        values = await self.prepare_update(db, obj, values)
        for key, value in values.items():
            setattr(obj, key, value)
        await self._flush(db, "update")
        await self._audit(db, "UPDATE", obj, sorted(data.model_fields_set))
        await db.commit()
        return await self.get(db, item_id)

    async def delete(self, db: AsyncSession, item_id: int) -> None:
        obj = await self.get(db, item_id)
        await self.before_delete(db, obj)
        await db.delete(obj)
        await self._flush(db, "delete")
        await self._audit(db, "DELETE", obj, None)
        await db.commit()

    # ----- utilitaires -------------------------------------------------------
    def _reject_null_on_required(self, values: dict[str, Any]) -> None:
        columns = inspect(self.model).columns
        for key, value in values.items():
            if value is None and key in columns and not columns[key].nullable:
                raise UnprocessableError("Ce champ ne peut pas être vide.", field=key)

    async def _flush(self, db: AsyncSession, operation: str) -> None:
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise translate_integrity_error(exc, operation) from exc

    async def _audit(self, db: AsyncSession, action: str, obj: ModelT, fields: list[str] | None) -> None:
        details = {"champs": [f for f in fields if _SECRET not in f]} if fields is not None else None
        await audit_service.record(
            db, action, self.model.__tablename__, obj.id, details  # type: ignore[attr-defined]
        )
