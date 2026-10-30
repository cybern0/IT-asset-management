# Boite d'envoi des notifications (parc_10.sql) : liens mailto: / sms: / wa.me prets a ouvrir, sans serveur de messagerie
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class Notification(IdMixin, Base):
    __tablename__ = "notification"

    fiche_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiche_detention.id", ondelete="CASCADE"))
    evenement: Mapped[str] = mapped_column(String(30))
    destinataire_agent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("agent.id"))
    destinataire_utilisateur_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    canal: Mapped[str] = mapped_column(String(12))  # APPLICATION | MAIL | SMS | WHATSAPP
    adresse: Mapped[str | None] = mapped_column(String(180))
    sujet: Mapped[str | None] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    lien: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(10), server_default=text("'A_ENVOYER'"))
    cree_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    envoye_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lu_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
