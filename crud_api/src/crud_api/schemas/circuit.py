# Affectation directe : un materiel deja detenu est retire a son detenteur et donne a un autre agent
from typing import Literal

from pydantic import BaseModel

from crud_api.schemas.common import OptDate, OptText


class TransfertCreate(BaseModel):
    """Affectation directe par le depositaire comptable : le materiel est retire a son detenteur et donne a `agent_id`."""

    materiel_id: int
    agent_id: int
    date: OptDate = None  # defaut : aujourd'hui
    etat: Literal["NEUF", "BON", "A_REPARER"] | None = None  # etat constate a la remise (defaut : etat du materiel)
    observations: OptText = None
