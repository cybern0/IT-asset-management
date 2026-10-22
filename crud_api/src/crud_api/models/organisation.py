# Direction -> Service -> Agent
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column

from crud_api.core.database import Base
from crud_api.models._mixins import IdMixin


class Direction(IdMixin, Base):
    __tablename__ = "direction"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    nom: Mapped[str] = mapped_column(String(180))
    actif: Mapped[bool] = mapped_column(Boolean, server_default=true())


class Service(IdMixin, Base):
    __tablename__ = "service"

    direction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("direction.id"))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    nom: Mapped[str] = mapped_column(String(180))
    site: Mapped[str | None] = mapped_column(String(150))
    actif: Mapped[bool] = mapped_column(Boolean, server_default=true())


class Agent(IdMixin, Base):
    __tablename__ = "agent"

    matricule: Mapped[str] = mapped_column(String(50), unique=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    fonction: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(180))
    service_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service.id"))
    actif: Mapped[bool] = mapped_column(Boolean, server_default=true())
