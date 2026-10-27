from fastapi import APIRouter, Depends

from crud_api.core.deps import ADMIN, GESTIONNAIRE, LECTURE, get_current_user, require_roles
from crud_api.routers import audit, auth, dashboard, fiches
from crud_api.routers.crud import crud_router
from crud_api.schemas import consommable as c
from crud_api.schemas import logiciel as lg
from crud_api.schemas import materiel as m
from crud_api.schemas import organisation as o
from crud_api.schemas import user as u
from crud_api.services.consommable_service import article_service, mouvement_service, stock_service
from crud_api.services.logiciel_service import licence_service, logiciel_service
from crud_api.services.materiel_service import affectation_service, categorie_service, materiel_service
from crud_api.services.organisation_service import agent_service, direction_service, service_service
from crud_api.services.role_service import permission_service, role_service
from crud_api.services.user_service import user_service

# Authentification : /auth/login est public
auth_router = auth.router

# Toutes les autres routes passent par get_current_user (ouvert tant que AUTH_ENABLED=false)
api_router = APIRouter(dependencies=[Depends(get_current_user)])

# Autorisation par role. L'interface (nav_ui/app/lib/access.ts) applique les memes regles a l'ecran.
#   ADMIN        : tout
#   GESTIONNAIRE : lecture + creation/modification du parc ; ni suppression, ni administration
#   LECTURE      : lecture seule (standard)
_EVERYONE = frozenset({ADMIN, GESTIONNAIRE, LECTURE})
_STAFF = frozenset({ADMIN, GESTIONNAIRE})
_ADMINS = frozenset({ADMIN})

_assets = Depends(require_roles(read=_EVERYONE, write=_STAFF, delete=_ADMINS))  # materiel, stocks, logiciels...
_organisation = Depends(require_roles(read=_EVERYONE, write=_ADMINS))  # agents, services : lus partout, geres par l'admin
_admin_only = Depends(require_roles(read=_ADMINS, write=_ADMINS))  # comptes, roles, permissions, journal d'audit
_policy = {
    "/directions": _organisation, "/services": _organisation, "/agents": _organisation,
    "/utilisateurs": _admin_only, "/roles": _admin_only, "/permissions": _admin_only,
}

_resources = [
    # (prefixe, tag, service, schema creation, schema modification, schema sortie, immuable)
    ("/directions", "Directions", direction_service, o.DirectionCreate, o.DirectionUpdate, o.DirectionOut, False),
    ("/services", "Services", service_service, o.ServiceCreate, o.ServiceUpdate, o.ServiceOut, False),
    ("/agents", "Agents", agent_service, o.AgentCreate, o.AgentUpdate, o.AgentOut, False),
    ("/utilisateurs", "Utilisateurs", user_service, u.UserCreate, u.UserUpdate, u.UserOut, False),
    ("/roles", "Rôles", role_service, u.RoleCreate, u.RoleUpdate, u.RoleOut, False),
    ("/permissions", "Permissions", permission_service, u.PermissionCreate, u.PermissionUpdate, u.PermissionOut, False),
    ("/categories-materiel", "Catégories de matériel", categorie_service, m.CategorieCreate, m.CategorieUpdate, m.CategorieOut, False),
    ("/materiels", "Matériel", materiel_service, m.MaterielCreate, m.MaterielUpdate, m.MaterielOut, False),
    ("/affectations", "Affectations", affectation_service, m.AffectationCreate, m.AffectationUpdate, m.AffectationOut, False),
    ("/articles-consommables", "Articles consommables", article_service, c.ArticleCreate, c.ArticleUpdate, c.ArticleOut, False),
    ("/stocks", "Stocks", stock_service, c.StockCreate, c.StockUpdate, c.StockOut, False),
    ("/mouvements", "Mouvements de stock", mouvement_service, c.MouvementCreate, c.MouvementCreate, c.MouvementOut, True),
    ("/logiciels", "Logiciels", logiciel_service, lg.LogicielCreate, lg.LogicielUpdate, lg.LogicielOut, False),
    ("/licences", "Licences", licence_service, lg.LicenceCreate, lg.LicenceUpdate, lg.LicenceOut, False),
]

for prefix, tag, service, create, update, out, immutable in _resources:
    api_router.include_router(
        crud_router(service=service, create_schema=create, update_schema=update, out_schema=out, immutable=immutable),
        prefix=prefix,
        tags=[tag],
        dependencies=[_policy.get(prefix, _assets)],
    )

api_router.include_router(fiches.router, dependencies=[_assets])
api_router.include_router(
    dashboard.router, prefix="/dashboard", tags=["Tableau de bord"],
    dependencies=[Depends(require_roles(read=_EVERYONE, write=_ADMINS))],
)
api_router.include_router(audit.router, prefix="/journal-audit", tags=["Journal d'audit"], dependencies=[_admin_only])
