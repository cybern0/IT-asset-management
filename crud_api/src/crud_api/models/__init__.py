from crud_api.models.consommable import ArticleConsommable, MouvementConsommable, StockConsommable
from crud_api.models.fiche import FicheDetention
from crud_api.models.logiciel import Licence, Logiciel
from crud_api.models.materiel import Affectation, CategorieMateriel, Materiel
from crud_api.models.notification import Notification
from crud_api.models.organisation import Agent, Direction, Service
from crud_api.models.user import Permission, Role, Utilisateur, role_permission

__all__ = [
    "Affectation", "Agent", "ArticleConsommable", "CategorieMateriel", "Direction", "FicheDetention",
    "Licence", "Logiciel", "Materiel", "MouvementConsommable", "Notification", "Permission", "Role", "Service",
    "StockConsommable", "Utilisateur", "role_permission",
]
