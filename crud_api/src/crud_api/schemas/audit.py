from datetime import datetime
from typing import Any

from pydantic import IPvAnyAddress

from crud_api.schemas.common import ORMModel


class AuditOut(ORMModel):
    id: int
    utilisateur_id: int | None
    action: str
    table_cible: str | None
    identifiant_cible: int | None
    details: Any | None
    adresse_ip: IPvAnyAddress | None
    cree_le: datetime
