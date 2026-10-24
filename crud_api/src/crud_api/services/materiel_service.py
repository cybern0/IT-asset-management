# Categories, materiel et affectations (cycle de vie du statut du materiel)
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import ConflictError, UnprocessableError
from crud_api.models import Affectation, Agent, CategorieMateriel, FicheDetention, Materiel
from crud_api.services import fiche_service
from crud_api.services.base import CRUDService

# Etat du materiel au retour -> nouveau statut
_STATUT_APRES_RETOUR = {"REFORME": "REFORME", "EN_PANNE": "EN_MAINTENANCE", "A_REPARER": "EN_MAINTENANCE"}


class CategorieService(CRUDService[CategorieMateriel]):
    model = CategorieMateriel
    label = "Catégorie"


class MaterielService(CRUDService[Materiel]):
    model = Materiel
    label = "Matériel"

    async def _has_active_assignment(self, db: AsyncSession, materiel_id: int) -> bool:
        stmt = select(Affectation.id).where(
            Affectation.materiel_id == materiel_id, Affectation.date_retour.is_(None)
        )
        return (await db.scalar(stmt)) is not None

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("statut") == "ATTRIBUE":
            raise UnprocessableError(
                "Le statut « Attribué » s’obtient en créant une affectation.", field="statut"
            )
        return values

    async def prepare_update(self, db: AsyncSession, obj: Materiel, values: dict[str, Any]) -> dict[str, Any]:
        if "statut" in values:
            active = await self._has_active_assignment(db, obj.id)
            if values["statut"] == "ATTRIBUE" and not active:
                raise UnprocessableError(
                    "Le statut « Attribué » s’obtient en créant une affectation.", field="statut"
                )
            if active and values["statut"] != "ATTRIBUE":
                raise ConflictError(
                    "Ce matériel est affecté : enregistrez d’abord le retour.", field="statut"
                )
        return values


class AffectationService(CRUDService[Affectation]):
    model = Affectation
    label = "Affectation"

    async def _materiel(self, db: AsyncSession, materiel_id: int) -> Materiel:
        materiel = await db.get(Materiel, materiel_id)
        if materiel is None:
            raise UnprocessableError("Matériel introuvable.", field="materiel_id")
        return materiel

    async def _agent(self, db: AsyncSession, agent_id: int) -> Agent:
        agent = await db.get(Agent, agent_id)
        if agent is None:
            raise UnprocessableError("Agent introuvable.", field="agent_id")
        if not agent.actif:
            raise UnprocessableError("Cet agent est inactif.", field="agent_id")
        return agent

    @staticmethod
    def _apply_return(materiel: Materiel, etat_retour: str | None) -> str:
        """Le materiel revient en stock, ou part en maintenance / reforme selon son etat."""
        etat = etat_retour or materiel.etat
        materiel.etat = etat
        materiel.statut = _STATUT_APRES_RETOUR.get(etat, "EN_STOCK")
        return etat

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        materiel = await self._materiel(db, values["materiel_id"])
        await self._agent(db, values["agent_id"])

        values["date_remise"] = values.get("date_remise") or date.today()
        retour = values.get("date_retour")
        if retour is not None and retour < values["date_remise"]:
            raise UnprocessableError("Le retour ne peut pas précéder la remise.", field="date_retour")

        if values.get("cree_par") is None:
            values["cree_par"] = db.info.get("actor_id")
        if values.get("etat_remise") is None:
            values["etat_remise"] = materiel.etat

        if retour is None:
            # affectation en cours : le materiel doit etre disponible
            if materiel.statut != "EN_STOCK":
                raise ConflictError(
                    f"Ce matériel n’est pas disponible (statut : {materiel.statut}).", field="materiel_id"
                )
            materiel.statut = "ATTRIBUE"
        else:
            # saisie d'une affectation deja terminee (historique) : le statut du materiel ne change pas
            values.setdefault("etat_retour", None)
        return values

    async def prepare_update(self, db: AsyncSession, obj: Affectation, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("materiel_id") not in (None, obj.materiel_id):
            raise UnprocessableError(
                "Le matériel d’une affectation ne peut pas changer : créez une nouvelle affectation.",
                field="materiel_id",
            )
        values.pop("materiel_id", None)
        if values.get("agent_id") not in (None, obj.agent_id):
            await self._agent(db, values["agent_id"])

        remise = values.get("date_remise") or obj.date_remise
        if "date_remise" in values and values["date_remise"] is None:
            values.pop("date_remise")  # NOT NULL : on garde la valeur existante
        retour = values.get("date_retour", obj.date_retour)
        if retour is not None and retour < remise:
            raise UnprocessableError("Le retour ne peut pas précéder la remise.", field="date_retour")

        if "date_retour" in values:
            if obj.date_retour is not None and values["date_retour"] is None:
                raise ConflictError(
                    "Impossible de rouvrir une affectation rendue : créez une nouvelle affectation.",
                    field="date_retour",
                )
            if obj.date_retour is None and values["date_retour"] is not None:
                materiel = await self._materiel(db, obj.materiel_id)
                values["etat_retour"] = self._apply_return(materiel, values.get("etat_retour"))
        return values

    async def after_create(self, db: AsyncSession, obj: Affectation) -> None:
        # chaine : affectation -> fiche de detention (NON_SIGNEE), dans la meme transaction
        await fiche_service.ensure_for_affectation(db, obj.id)

    async def before_delete(self, db: AsyncSession, obj: Affectation) -> None:
        fiche = await db.scalar(select(FicheDetention).where(FicheDetention.affectation_id == obj.id))
        if fiche is not None and fiche.statut == "SIGNEE":
            raise ConflictError(
                "Cette affectation a une fiche signée (conservation 5 ans) : annulez d’abord la signature."
            )
        if obj.date_retour is None:
            materiel = await db.get(Materiel, obj.materiel_id)
            if materiel is not None and materiel.statut == "ATTRIBUE":
                materiel.statut = "EN_STOCK"


categorie_service = CategorieService()
materiel_service = MaterielService()
affectation_service = AffectationService()
