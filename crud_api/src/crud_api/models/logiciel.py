# Logiciels et licences (parc_2.sql)
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class Logiciel(IdMixin, Base):
    __tablename__ = "logiciel"

    nom: Mapped[str] = mapped_column(String(180))
    editeur: Mapped[str | None] = mapped_column(String(150))
    version: Mapped[str | None] = mapped_column(String(60))
    type_licence: Mapped[str] = mapped_column(String(20), server_default=text("'PERPETUELLE'"))
    observations: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Licence(IdMixin, Base):
    __tablename__ = "licence"

    logiciel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("logiciel.id"))
    cle_licence: Mapped[str | None] = mapped_column(String(255))
    nombre_postes: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    date_expiration: Mapped[date | None] = mapped_column(Date)
    observations: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
