from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_item_service
from app.models import ItemCreate
from app.schemas import ItemIn, ItemOut, ListResponse
from app.services.item_service import ItemService

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.post(
    "",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    payload: ItemIn,
    service: ItemService = Depends(get_item_service),
) -> ItemOut:
    try:
        item = await service.create(
            ItemCreate(name=payload.name, category=payload.category, value=payload.value)
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return ItemOut(
        id=item.id,
        name=item.name,
        category=item.category,
        value=item.value,
        created_at=item.created_at,
    )


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
) -> ItemOut:
    item = await service.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return ItemOut(
        id=item.id,
        name=item.name,
        category=item.category,
        value=item.value,
        created_at=item.created_at,
    )


@router.get("", response_model=ListResponse)
async def list_items(
    category: str | None = Query(default=None),
    cursor: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    service: ItemService = Depends(get_item_service),
) -> ListResponse:
    page = await service.list(category=category, cursor=cursor, limit=limit)
    return ListResponse(
        items=[
            ItemOut(
                id=i.id,
                name=i.name,
                category=i.category,
                value=i.value,
                created_at=i.created_at,
            )
            for i in page.rows
        ],
        next_cursor=page.next_cursor,
    )
