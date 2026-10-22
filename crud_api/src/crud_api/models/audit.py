# Journal d'audit (parc_3.sql) : ecrit par les services, jamais par l'utilisateur
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class JournalAudit(IdMixin, Base):
    __tablename__ = "journal_audit"

    utilisateur_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    action: Mapped[str] = mapped_column(String(80))
    table_cible: Mapped[str | None] = mapped_column(String(100))
    identifiant_cible: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[Any | None] = mapped_column(JSONB)
    adresse_ip: Mapped[str | None] = mapped_column(INET)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
