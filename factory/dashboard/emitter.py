"""EventEmitter — fire-and-forget event posting to the Status API.

Dashboard failures must never block or crash the orchestrator.
"""

from __future__ import annotations

import logging
import os

import httpx

from factory.dashboard.models import EventIn

LOG = logging.getLogger(__name__)


class EventEmitter:
    """Posts lifecycle events to the Dashboard Status API.

    If DASHBOARD_URL env var is not set or empty, all emit_* methods
    are silent no-ops.
    """

    def __init__(self) -> None:
        self._base_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")

    @property
    def enabled(self) -> bool:
        """Return True if the emitter is active."""
        return bool(self._base_url)

    async def _post_event(self, event: EventIn) -> None:
        """POST an event payload. Swallows all errors."""
        if not self.enabled:
            return

        url = f"{self._base_url}/api/v1/events"
        LOG.debug("Emitting %s for task %s", event.event_type, event.task_id)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=event.model_dump())
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            LOG.error(
                "Failed to emit %s for task %s: %s",
                event.event_type,
                event.task_id,
                exc,
            )

    async def emit_job_started(self, repo: str, issue_number: int) -> None:
        """Emit job_started event."""
        task_id = f"{repo}#{issue_number}"
        event = EventIn(
            task_id=task_id,
            event_type="job_started",
            status="pending",
        )
        await self._post_event(event)

    async def emit_job_completed(self, repo: str, issue_number: int) -> None:
        """Emit job_completed event."""
        task_id = f"{repo}#{issue_number}"
        event = EventIn(
            task_id=task_id,
            event_type="job_completed",
            status="success",
        )
        await self._post_event(event)

    async def emit_job_failed(self, repo: str, issue_number: int) -> None:
        """Emit job_failed event."""
        task_id = f"{repo}#{issue_number}"
        event = EventIn(
            task_id=task_id,
            event_type="job_failed",
            status="failure",
        )
        await self._post_event(event)

    async def emit_agent_spawned(self, task_id: str, agent_type: str) -> None:
        """Emit agent_spawned event."""
        event = EventIn(
            task_id=task_id,
            event_type="agent_spawned",
            status="pending",
            message=agent_type,
        )
        await self._post_event(event)

    async def emit_agent_exited(
        self, task_id: str, agent_type: str, *, success: bool
    ) -> None:
        """Emit agent_exited event."""
        status = "success" if success else "failure"
        event = EventIn(
            task_id=task_id,
            event_type="agent_exited",
            status=status,
            message=agent_type,
        )
        await self._post_event(event)

    async def emit_task_started(self, task_id: str) -> None:
        """Emit task_started event."""
        event = EventIn(
            task_id=task_id,
            event_type="task_started",
            status="pending",
        )
        await self._post_event(event)

    async def emit_task_completed(self, task_id: str) -> None:
        """Emit task_completed event."""
        event = EventIn(
            task_id=task_id,
            event_type="task_completed",
            status="success",
        )
        await self._post_event(event)

    async def emit_task_failed(self, task_id: str) -> None:
        """Emit task_failed event."""
        event = EventIn(
            task_id=task_id,
            event_type="task_failed",
            status="failure",
        )
        await self._post_event(event)

    async def emit_round_result(
        self, task_id: str, round_num: int, *, passed: bool
    ) -> None:
        """Emit round_result event."""
        status = "success" if passed else "failure"
        event = EventIn(
            task_id=task_id,
            event_type="round_result",
            status=status,
            message=f"round {round_num}",
        )
        await self._post_event(event)
