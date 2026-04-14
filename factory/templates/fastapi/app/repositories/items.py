from __future__ import annotations

import time
from dataclasses import dataclass

import aiosqlite

from app.models import Item, ItemCreate


@dataclass(slots=True)
class ListPage:
    rows: list[Item]
    next_cursor: int | None


class ItemRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, data: ItemCreate) -> Item:
        now = time.time()
        async with self._conn.execute(
            "INSERT INTO items (name, category, value, created_at) VALUES (?, ?, ?, ?)",
            (data.name, data.category, data.value, now),
        ) as cur:
            item_id = cur.lastrowid
        await self._conn.commit()
        assert item_id is not None
        return Item(
            id=item_id,
            name=data.name,
            category=data.category,
            value=data.value,
            created_at=now,
        )

    async def get(self, item_id: int) -> Item | None:
        async with self._conn.execute(
            "SELECT id, name, category, value, created_at FROM items WHERE id = ?",
            (item_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return Item(
            id=int(row["id"]),
            name=row["name"],
            category=row["category"],
            value=float(row["value"]),
            created_at=float(row["created_at"]),
        )

    async def list(
        self,
        *,
        category: str | None,
        cursor: int | None,
        limit: int,
    ) -> ListPage:
        where: list[str] = []
        params: list[object] = []
        if category is not None:
            where.append("category = ?")
            params.append(category)
        if cursor is not None:
            where.append("id < ?")
            params.append(cursor)

        sql = "SELECT id, name, category, value, created_at FROM items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit + 1)

        rows: list[Item] = []
        async with self._conn.execute(sql, params) as cur:
            async for row in cur:
                rows.append(
                    Item(
                        id=int(row["id"]),
                        name=row["name"],
                        category=row["category"],
                        value=float(row["value"]),
                        created_at=float(row["created_at"]),
                    )
                )

        next_cursor: int | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]
        return ListPage(rows=rows, next_cursor=next_cursor)

    async def count(self) -> int:
        async with self._conn.execute("SELECT COUNT(*) FROM items") as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0
