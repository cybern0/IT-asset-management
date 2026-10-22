# Articles, stocks par service et mouvements (les mouvements mettent les stocks a jour)
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.core.errors import ConflictError, UnprocessableError
from crud_api.models import ArticleConsommable, MouvementConsommable, StockConsommable
from crud_api.services.base import CRUDService


class ArticleService(CRUDService[ArticleConsommable]):
    model = ArticleConsommable
    label = "Article"


def _same_service(service_id: int | None):
    """service_id NULL = stock central."""
    column = StockConsommable.service_id
    return column.is_(None) if service_id is None else column == service_id


class StockService(CRUDService[StockConsommable]):
    model = StockConsommable
    label = "Stock"

    async def _ensure_unique(
        self, db: AsyncSession, article_id: int, service_id: int | None, exclude_id: int | None = None
    ) -> None:
        stmt = select(StockConsommable.id).where(
            StockConsommable.article_id == article_id, _same_service(service_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(StockConsommable.id != exclude_id)
        if (await db.scalar(stmt.limit(1))) is not None:
            raise ConflictError(
                "Un stock existe déjà pour cet article et ce service.", field="article_id"
            )

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_unique(db, values["article_id"], values.get("service_id"))
        return values

    async def prepare_update(self, db: AsyncSession, obj: StockConsommable, values: dict[str, Any]) -> dict[str, Any]:
        if "article_id" in values or "service_id" in values:
            await self._ensure_unique(
                db,
                values.get("article_id", obj.article_id),
                values.get("service_id", obj.service_id),
                exclude_id=obj.id,
            )
        return values


class MouvementService(CRUDService[MouvementConsommable]):
    """Un mouvement est immuable : on le cree, on ne le modifie ni ne le supprime."""

    model = MouvementConsommable
    label = "Mouvement"

    async def _apply(self, db: AsyncSession, article_id: int, service_id: int | None, delta: Decimal) -> None:
        stmt = (
            select(StockConsommable)
            .where(StockConsommable.article_id == article_id, _same_service(service_id))
            .with_for_update()
        )
        stock = (await db.scalars(stmt)).first()
        if stock is None:
            if delta < 0:
                raise ConflictError("Stock insuffisant : aucun stock pour cet article.", field="quantite")
            stock = StockConsommable(article_id=article_id, service_id=service_id, quantite=Decimal(0))
            db.add(stock)
        new_quantity = stock.quantite + delta
        if new_quantity < 0:
            raise ConflictError(
                f"Stock insuffisant : {stock.quantite} disponible(s).", field="quantite"
            )
        stock.quantite = new_quantity

    async def prepare_create(self, db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
        article = await db.get(ArticleConsommable, values["article_id"])
        if article is None:
            raise UnprocessableError("Article introuvable.", field="article_id")
        if not article.actif:
            raise UnprocessableError("Cet article est inactif.", field="article_id")

        kind = values["type_mouvement"]
        source, destination = values.get("service_source_id"), values.get("service_destination_id")
        quantity: Decimal = values["quantite"]

        if values.get("provenance") and kind != "ENTREE":
            raise UnprocessableError("La provenance ne concerne que les entrées.", field="provenance")
        if values.get("effectue_par") is None:
            values["effectue_par"] = db.info.get("actor_id")
            if values["effectue_par"] is None:
                raise UnprocessableError("L’auteur du mouvement est obligatoire.", field="effectue_par")

        # service NULL = stock central
        if kind == "ENTREE":
            if source is not None:
                raise UnprocessableError("Une entrée n’a pas de service source.", field="service_source_id")
            await self._apply(db, article.id, destination, quantity)
        elif kind == "SORTIE":
            if destination is not None:
                raise UnprocessableError(
                    "Une sortie n’a pas de service destination.", field="service_destination_id"
                )
            await self._apply(db, article.id, source, -quantity)
        elif kind == "TRANSFERT":
            if source == destination:
                raise UnprocessableError(
                    "La source et la destination doivent être différentes.", field="service_destination_id"
                )
            await self._apply(db, article.id, source, -quantity)
            await self._apply(db, article.id, destination, quantity)
        else:  # AJUSTEMENT : retire du service source s'il est indique, sinon ajoute a la destination
            if source is not None and destination is not None:
                raise UnprocessableError(
                    "Un ajustement ne concerne qu’un seul service.", field="service_destination_id"
                )
            if source is not None:
                await self._apply(db, article.id, source, -quantity)
            else:
                await self._apply(db, article.id, destination, quantity)
        return values


article_service = ArticleService()
stock_service = StockService()
mouvement_service = MouvementService()
