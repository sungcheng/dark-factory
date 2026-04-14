from __future__ import annotations

from app.models import ItemCreate
from app.repositories.items import ItemRepository


class TestCreateAndGet:
    async def test_create_then_get_returns_same_item(self, item_repo: ItemRepository) -> None:
        created = await item_repo.create(ItemCreate(name="Widget", category="tools", value=9.99))
        fetched = await item_repo.get(created.id)
        assert fetched is not None
        assert fetched.name == "Widget"
        assert fetched.category == "tools"
        assert fetched.value == 9.99

    async def test_get_unknown_id_returns_none(self, item_repo: ItemRepository) -> None:
        result = await item_repo.get(99999)
        assert result is None


class TestList:
    async def test_list_returns_all_items_when_no_filter(self, item_repo: ItemRepository) -> None:
        for i in range(3):
            await item_repo.create(ItemCreate(name=f"Item-{i}", category="a"))
        page = await item_repo.list(category=None, cursor=None, limit=50)
        assert len(page.rows) == 3
        assert page.next_cursor is None

    async def test_list_filters_by_category(self, item_repo: ItemRepository) -> None:
        await item_repo.create(ItemCreate(name="X", category="books"))
        await item_repo.create(ItemCreate(name="Y", category="tools"))
        await item_repo.create(ItemCreate(name="Z", category="books"))
        page = await item_repo.list(category="books", cursor=None, limit=50)
        assert len(page.rows) == 2
        assert all(r.category == "books" for r in page.rows)

    async def test_list_paginates_with_cursor(self, item_repo: ItemRepository) -> None:
        for i in range(5):
            await item_repo.create(ItemCreate(name=f"N{i}"))
        page1 = await item_repo.list(category=None, cursor=None, limit=2)
        assert len(page1.rows) == 2
        assert page1.next_cursor is not None
        page2 = await item_repo.list(category=None, cursor=page1.next_cursor, limit=2)
        assert len(page2.rows) == 2
        ids1 = {r.id for r in page1.rows}
        ids2 = {r.id for r in page2.rows}
        assert ids1.isdisjoint(ids2)

    async def test_count_reflects_inserts(self, item_repo: ItemRepository) -> None:
        assert await item_repo.count() == 0
        await item_repo.create(ItemCreate(name="A"))
        await item_repo.create(ItemCreate(name="B"))
        assert await item_repo.count() == 2
