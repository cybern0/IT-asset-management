# Roles (avec leurs permissions : table role_permission) et permissions
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import UnprocessableError
from crud_api.models import Permission, Role
from crud_api.services.base import CRUDService


class PermissionService(CRUDService[Permission]):
    model = Permission
    label = "Permission"


class RoleService(CRUDService[Role]):
    model = Role
    label = "Rôle"

    async def _load_permissions(self, db: AsyncSession, ids: list[int]) -> list[Permission]:
        wanted = set(ids)
        found = list((await db.scalars(select(Permission).where(Permission.id.in_(wanted)))).all()) if wanted else []
        missing = wanted - {p.id for p in found}
        if missing:
            raise UnprocessableError(
                f"Permission(s) introuvable(s) : {sorted(missing)}", field="permission_ids"
            )
        return sorted(found, key=lambda p: p.id)

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        values["permissions"] = await self._load_permissions(db, values.pop("permission_ids", []))
        return values

    async def prepare_update(self, db: AsyncSession, obj: Role, values: dict[str, Any]) -> dict[str, Any]:
        if "permission_ids" in values:
            ids = values.pop("permission_ids") or []
            values["permissions"] = await self._load_permissions(db, ids)
        return values


permission_service = PermissionService()
role_service = RoleService()
