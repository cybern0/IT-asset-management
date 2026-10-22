# Consommables : articles, stocks par service, mouvements
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, func, text, true
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class ArticleConsommable(IdMixin, Base):
    __tablename__ = "article_consommable"

    reference: Mapped[str] = mapped_column(String(60), unique=True)
    designation: Mapped[str] = mapped_column(String(180))
    categorie: Mapped[str | None] = mapped_column(String(100))
    unite: Mapped[str] = mapped_column(String(30), server_default=text("'unite'"))
    seuil_alerte: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default=text("0"))
    actif: Mapped[bool] = mapped_column(Boolean, server_default=true())


class StockConsommable(IdMixin, Base):
    __tablename__ = "stock_consommable"

    article_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("article_consommable.id"))
    service_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service.id"))  # NULL = stock central
    quantite: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default=text("0"))


class MouvementConsommable(IdMixin, Base):
    __tablename__ = "mouvement_consommable"

    article_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("article_consommable.id"))
    service_source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service.id"))
    service_destination_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service.id"))
    type_mouvement: Mapped[str] = mapped_column(String(20))
    quantite: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reference_document: Mapped[str | None] = mapped_column(String(100))
    provenance: Mapped[str | None] = mapped_column(String(20))
    motif: Mapped[str] = mapped_column(Text)
    effectue_par: Mapped[int] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
