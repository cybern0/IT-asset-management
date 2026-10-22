# Comptes et autorisations : utilisateur, role, permission, role_permission
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Table, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(IdMixin, Base):
    __tablename__ = "permission"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    libelle: Mapped[str] = mapped_column(String(180))


class Role(IdMixin, Base):
    __tablename__ = "role"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    libelle: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permission, lazy="selectin", order_by=Permission.id
    )

    @property
    def permission_ids(self) -> list[int]:
        return [p.id for p in self.permissions]


class Utilisateur(IdMixin, Base):
    __tablename__ = "utilisateur"

    agent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("agent.id"))
    nom_utilisateur: Mapped[str] = mapped_column(String(80), unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(Text)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("role.id"))
    actif: Mapped[bool] = mapped_column(Boolean, server_default=true())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
