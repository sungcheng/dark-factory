from __future__ import annotations

import logging

from app.models import Item, ItemCreate
from app.repositories.items import ItemRepository, ListPage

LOG = logging.getLogger(__name__)


class ItemService:
    """Business logic for items. Stays thin — routers call this, not the repo."""

    def __init__(self, repo: ItemRepository) -> None:
        self._repo = repo

    async def create(self, data: ItemCreate) -> Item:
        if not data.name.strip():
            raise ValueError("name cannot be blank")
        item = await self._repo.create(data)
        LOG.info("created item", extra={"item_id": item.id, "category": item.category})
        return item

    async def get(self, item_id: int) -> Item | None:
        return await self._repo.get(item_id)

    async def list(
        self,
        *,
        category: str | None,
        cursor: int | None,
        limit: int,
    ) -> ListPage:
        return await self._repo.list(category=category, cursor=cursor, limit=limit)
