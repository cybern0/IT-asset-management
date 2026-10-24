# Fiche de detention : une par affectation
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class FicheDetention(IdMixin, Base):
    __tablename__ = "fiche_detention"

    affectation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("affectation.id", ondelete="CASCADE"), unique=True
    )
    reference: Mapped[str] = mapped_column(String(30), unique=True)
    statut: Mapped[str] = mapped_column(String(15), server_default=text("'NON_SIGNEE'"))
    date_signature: Mapped[date | None] = mapped_column(Date)
    fichier_signe_chemin: Mapped[str | None] = mapped_column(String(255))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
