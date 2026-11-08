from fastapi import APIRouter, Depends

from crud_api.core.deps import get_current_user, require_perms, requires
from crud_api.routers import audit, auth, circuit, dashboard, fiches, tracabilite
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
from crud_api.services.user_service import user_service

# Authentification : /auth/login est public
auth_router = auth.router

# Toutes les autres routes passent par get_current_user (ouvert tant que AUTH_ENABLED=false)
api_router = APIRouter(dependencies=[Depends(get_current_user)])

# Autorisation par PERMISSIONS (tables permission / role_permission, parc_10.sql) : changer les droits d'un role ne
# demande aucune modification du code. L'interface recoit la liste des permissions (/auth/login, /auth/me).
def _p(*codes: str) -> frozenset[str]:
    return frozenset(codes)


_assets = Depends(require_perms(read=_p("parc.lire"), write=_p("parc.ecrire"), delete=_p("parc.supprimer")))  # materiel, stocks, logiciels...
_organisation = Depends(require_perms(read=_p("parc.lire"), write=_p("parc.ecrire")))  # agents, services
_admin_only = Depends(require_perms(read=_p("acces.gerer"), write=_p("acces.gerer")))  # comptes utilisateurs (un seul role : ADMIN)
_policy = {
    "/directions": _organisation, "/services": _organisation, "/agents": _organisation,
    "/utilisateurs": _admin_only,
}

_resources = [
    # (prefixe, tag, service, schema creation, schema modification, schema sortie, immuable)
    ("/directions", "Directions", direction_service, o.DirectionCreate, o.DirectionUpdate, o.DirectionOut, False),
    ("/services", "Services", service_service, o.ServiceCreate, o.ServiceUpdate, o.ServiceOut, False),
    ("/agents", "Agents", agent_service, o.AgentCreate, o.AgentUpdate, o.AgentOut, False),
    ("/utilisateurs", "Utilisateurs", user_service, u.UserCreate, u.UserUpdate, u.UserOut, False),
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
api_router.include_router(circuit.router)  # circuit de demande : droits verifies route par route
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Tableau de bord"])  # droits par route
api_router.include_router(tracabilite.router, prefix="/tracabilite", tags=["Traçabilité"], dependencies=[_assets])  # vue Global > Materiel : parcours des materiels (lecture seule, meme droit que le parc : parc.lire)
api_router.include_router(audit.router, prefix="/journal-audit", tags=["Journal d'audit"], dependencies=[Depends(require_perms(read=_p("audit.lire"), write=_p("audit.lire")))])
