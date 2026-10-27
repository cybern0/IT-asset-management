# Categories, materiel individualise, affectations
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class CategorieMateriel(IdMixin, Base):
    __tablename__ = "categorie_materiel"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    libelle: Mapped[str] = mapped_column(String(100))
    # Menu dynamique : l'UI n'affiche l'onglet de cette categorie que si ce champ vaut TRUE
    afficher_menu: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)


class Materiel(IdMixin, Base):
    __tablename__ = "materiel"

    code_inventaire: Mapped[str] = mapped_column(String(60), unique=True)
    categorie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categorie_materiel.id"))
    designation: Mapped[str] = mapped_column(String(180))
    marque: Mapped[str | None] = mapped_column(String(100))
    modele: Mapped[str | None] = mapped_column(String(100))
    numero_serie: Mapped[str | None] = mapped_column(String(150), unique=True)
    caracteristiques: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(20), server_default=text("'ACHAT'"))
    provenance_detail: Mapped[str | None] = mapped_column(String(180))
    date_acquisition: Mapped[date | None] = mapped_column(Date)
    valeur_acquisition: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    etat: Mapped[str] = mapped_column(String(20), server_default=text("'BON'"))
    statut: Mapped[str] = mapped_column(String(25), server_default=text("'EN_STOCK'"))
    localisation: Mapped[str | None] = mapped_column(String(180))
    observations: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    image_chemin: Mapped[str | None] = mapped_column(String(255))

    categorie: Mapped[CategorieMateriel] = relationship(lazy="joined")

    @property
    def categorie_code(self) -> str:
        """Code de la categorie : l'UI s'en sert pour filtrer ses onglets."""
        return self.categorie.code

    @property
    def a_image(self) -> bool:
        """Le chemin du fichier reste cote serveur : l'UI ne voit que ce booleen."""
        return bool(self.image_chemin)


class Affectation(IdMixin, Base):
    __tablename__ = "affectation"

    materiel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materiel.id"))
    agent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("agent.id"))
    date_remise: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    date_retour: Mapped[date | None] = mapped_column(Date)
    etat_remise: Mapped[str | None] = mapped_column(String(20))
    etat_retour: Mapped[str | None] = mapped_column(String(20))
    observations: Mapped[str | None] = mapped_column(Text)
    cree_par: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("utilisateur.id"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
