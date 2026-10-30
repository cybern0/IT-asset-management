# Dossier d'attribution = fiche de detention (processus en 6 etapes, voir parc_5.sql)
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class FicheDetention(IdMixin, Base):
    __tablename__ = "fiche_detention"

    reference: Mapped[str] = mapped_column(String(30), unique=True)
    affectation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("affectation.id", ondelete="CASCADE"), unique=True
    )
    # coordonnees propres au dossier (parc_9.sql) : si vides, la fiche reprend celles de l'agent
    telephone: Mapped[str | None] = mapped_column(String(30))
    whatsapp: Mapped[str | None] = mapped_column(String(30))
    adresse_domicile_exacte: Mapped[str | None] = mapped_column(Text)
    # etape 1
    agent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("agent.id"))
    categorie_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categorie_materiel.id"))
    besoin: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(String(15), server_default=text("'FORMULAIRE'"))
    reference_canal: Mapped[str | None] = mapped_column(String(120))
    demandeur: Mapped[str | None] = mapped_column(String(150))
    date_demande: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    valide_par: Mapped[str | None] = mapped_column(String(150))
    date_validation: Mapped[date | None] = mapped_column(Date)
    # etapes 2-3
    materiel_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("materiel.id"))
    date_generation: Mapped[date | None] = mapped_column(Date)
    # etape 4
    statut: Mapped[str] = mapped_column(String(15), server_default=text("'NON_SIGNEE'"))
    date_signature: Mapped[date | None] = mapped_column(Date)
    mode_signature: Mapped[str | None] = mapped_column(String(15))
    signe_par: Mapped[str | None] = mapped_column(String(150))
    signature_modifiee_par: Mapped[str | None] = mapped_column(String(80))  # compte qui a fixe l'etat de signature
    signature_modifiee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # etape 5
    date_remise: Mapped[date | None] = mapped_column(Date)
    etat_constate: Mapped[str | None] = mapped_column(String(15))
    accessoires: Mapped[str | None] = mapped_column(String(200))
    accessoires_autre: Mapped[str | None] = mapped_column(String(100))
    observations_remise: Mapped[str | None] = mapped_column(Text)
    # circuit de demande (parc_10.sql)
    ancien_agent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("agent.id"))  # affectation : detenteur dont le materiel est retire
    ancienne_affectation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("affectation.id"))
    type_demande: Mapped[str] = mapped_column(String(12), server_default=text("'ATTRIBUTION'"))
    demande_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    approuve_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    approuve_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motif_refus: Mapped[str | None] = mapped_column(Text)
    signature_agent_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    signature_agent_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signature_chef_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    signature_chef_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reception_approuvee_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    reception_approuvee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # cloture avant la fin
    cloture: Mapped[str | None] = mapped_column(String(10))
    motif_cloture: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
