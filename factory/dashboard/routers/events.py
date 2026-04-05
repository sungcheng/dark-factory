from __future__ import annotations

from fastapi import APIRouter

from factory.dashboard.db import insert_event
from factory.dashboard.models import EventIn
from factory.dashboard.models import EventOut

router = APIRouter()


@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(event_in: EventIn) -> EventOut:
    """Create a new event in the database.

    Args:
        event_in: Event data from request body

    Returns:
        EventOut: Created event with server-generated id and timestamp
    """
    return await insert_event(event_in)
