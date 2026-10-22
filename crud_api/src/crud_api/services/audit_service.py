# Journal d'audit : ecriture (appelee par les autres services) et lecture
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.models import JournalAudit


async def record(
    db: AsyncSession,
    action: str,
    table: str | None = None,
    target_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Ajoute une ligne dans la transaction en cours (validee avec l'operation)."""
    db.add(
        JournalAudit(
            utilisateur_id=db.info.get("actor_id"),
            adresse_ip=db.info.get("ip"),
            action=action,
            table_cible=table,
            identifiant_cible=target_id,
            details=details,
        )
    )


async def list_entries(db: AsyncSession, *, limit: int = 500, offset: int = 0) -> list[JournalAudit]:
    stmt = select(JournalAudit).order_by(JournalAudit.cree_le.desc(), JournalAudit.id.desc())
    return list((await db.scalars(stmt.limit(limit).offset(offset))).all())
