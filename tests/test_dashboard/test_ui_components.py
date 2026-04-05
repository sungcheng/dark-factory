"""Tests for dashboard UI components — Phase 1 (RED).

Covers acceptance criteria for:
- AgentCards.tsx  — dynamic status from events, color-coded borders/badges
- TaskProgress.tsx — task list with per-round red/green indicators
- LiveLog.tsx      — 3-second polling, auto-scroll, color-coded entries
- JobHistory.tsx   — table with status badges, duration, row selection
- usePolling.ts    — custom hook with data/loading/error state
- App.tsx          — layout wiring, selectedJobId state management
- npm build        — TypeScript compilation with no errors
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "dashboard" / "frontend"
SRC = FRONTEND_ROOT / "src"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_component(name: str) -> str:
    path = SRC / "components" / name
    assert path.is_file(), f"src/components/{name} does not exist"
    return path.read_text()


def read_hook(name: str) -> str:
    path = SRC / "hooks" / name
    assert path.is_file(), f"src/hooks/{name} does not exist"
    return path.read_text()


# ===========================================================================
# AgentCards
# ===========================================================================


class TestAgentCards:
    """AgentCards displays agent status derived from events (not hardcoded)."""

    @pytest.fixture()
    def content(self) -> str:
        return read_component("AgentCards.tsx")

    # ---- props / data flow -------------------------------------------------

    def test_agent_cards_accepts_events_prop(self, content: str) -> None:
        """AgentCards must accept an `events` prop to derive agent status."""
        # Accepts interface/type with events field or function parameter with events
        assert re.search(r"events\s*[:\?]", content), (
            "AgentCards must accept an 'events' prop (events: Event[])"
        )

    def test_agent_cards_accepts_job_id_prop(self, content: str) -> None:
        """AgentCards must accept a jobId prop so it knows which job to reflect."""
        assert re.search(r"jobId\s*[:\?]|job_id\s*[:\?]", content), (
            "AgentCards must accept a jobId prop"
        )

    def test_agent_cards_derives_status_from_events(self, content: str) -> None:
        """AgentCards must derive agent status from events, not hardcode 'Idle'."""
        # Must not just output a static "Idle" string without any logic
        # i.e. must have some conditional/computed status logic
        has_logic = bool(
            re.search(
                r"(filter|find|reduce|map|switch|===|agent_started|agent_completed)",
                content,
            )
        )
        assert has_logic, (
            "AgentCards must derive status from events (filter/find/map on events), "
            "not return a static hardcoded string"
        )

    # ---- color coding -------------------------------------------------------

    def test_agent_cards_has_gray_idle_class(self, content: str) -> None:
        """Idle agent cards must use a gray border/badge Tailwind class."""
        has_gray = bool(re.search(r"gray-[4-7]00|border-gray|text-gray", content))
        assert has_gray, "AgentCards must use gray Tailwind classes for idle status"

    def test_agent_cards_has_blue_active_class(self, content: str) -> None:
        """Active agent cards must use a blue border/badge Tailwind class."""
        has_blue = bool(
            re.search(r"blue-[4-6]00|border-blue|text-blue|bg-blue", content)
        )
        assert has_blue, "AgentCards must use blue Tailwind classes for active status"

    def test_agent_cards_has_green_done_class(self, content: str) -> None:
        """Done agent cards must use a green border/badge Tailwind class."""
        has_green = bool(
            re.search(r"green-[4-6]00|border-green|text-green|bg-green", content)
        )
        assert has_green, "AgentCards must use green Tailwind classes for done status"

    def test_agent_cards_status_is_dynamic_not_static(self, content: str) -> None:
        """Status text must be computed, not hardcoded as the only value."""
        # The stub just returns <p>Idle</p>. A real implementation uses a variable.
        # Test: if there is any ternary / conditional expression OR the word 'Idle'
        # only appears inside a conditional (not as the sole possible value).
        hardcoded_only = bool(re.search(r">\s*Idle\s*<", content)) and not bool(
            re.search(r"[?:{}].*[Ii]dle|[Ii]dle.*[?:{}]", content)
        )
        assert not hardcoded_only, (
            "AgentCards status must be dynamically computed from events, "
            "not a hardcoded static 'Idle' string"
        )

    def test_agent_cards_imports_event_type(self, content: str) -> None:
        """AgentCards must import Event or EventType from types."""
        assert re.search(r"from\s+['\"].*types", content), (
            "AgentCards must import Event/EventType from types"
        )


# ===========================================================================
# TaskProgress
# ===========================================================================


class TestTaskProgress:
    """TaskProgress shows a task list with per-round red/green indicators."""

    @pytest.fixture()
    def content(self) -> str:
        return read_component("TaskProgress.tsx")

    def test_task_progress_accepts_job_detail_or_events(self, content: str) -> None:
        """TaskProgress must accept job data (tasks/events) as props."""
        has_prop = bool(
            re.search(r"(tasks|events|jobDetail|job_detail|rounds)\s*[:\?]", content)
        )
        assert has_prop, "TaskProgress must accept tasks/events/jobDetail prop"

    def test_task_progress_has_red_indicator_class(self, content: str) -> None:
        """TaskProgress must have red Tailwind classes for failed round indicators."""
        has_red = bool(re.search(r"red-[3-6]00|bg-red|text-red|border-red", content))
        assert has_red, (
            "TaskProgress must use red Tailwind classes for failed round indicators"
        )

    def test_task_progress_has_green_indicator_class(self, content: str) -> None:
        """TaskProgress must have green Tailwind classes for passed round indicators."""
        has_green = bool(
            re.search(r"green-[3-6]00|bg-green|text-green|border-green", content)
        )
        assert has_green, (
            "TaskProgress must use green Tailwind classes for passed round indicators"
        )

    def test_task_progress_renders_task_list(self, content: str) -> None:
        """TaskProgress must render a list/map of tasks, not a single progress bar."""
        has_list = bool(re.search(r"\.(map|forEach)\s*\(|<ul|<li|<ol", content))
        assert has_list, (
            "TaskProgress must render a list of tasks (map/forEach or ul/li elements), "
            "not just a single progress bar"
        )

    def test_task_progress_shows_round_results(self, content: str) -> None:
        """TaskProgress must reference round results (test_passed/test_failed events)."""
        has_rounds = bool(
            re.search(r"test_passed|test_failed|round|TEST_PASSED|TEST_FAILED", content)
        )
        assert has_rounds, (
            "TaskProgress must reference round results (test_passed/test_failed)"
        )

    def test_task_progress_imports_from_types(self, content: str) -> None:
        """TaskProgress must import types from types module."""
        assert re.search(r"from\s+['\"].*types", content), (
            "TaskProgress must import from types"
        )


# ===========================================================================
# LiveLog
# ===========================================================================


class TestLiveLog:
    """LiveLog polls every 3 seconds and auto-scrolls to bottom."""

    @pytest.fixture()
    def content(self) -> str:
        return read_component("LiveLog.tsx")

    def test_live_log_accepts_job_id_prop(self, content: str) -> None:
        """LiveLog must accept a jobId prop to know which log to poll."""
        assert re.search(r"jobId\s*[:\?]|job_id\s*[:\?]", content), (
            "LiveLog must accept a jobId prop"
        )

    def test_live_log_uses_polling_hook(self, content: str) -> None:
        """LiveLog must use the usePolling custom hook."""
        assert "usePolling" in content, "LiveLog must use the usePolling custom hook"

    def test_live_log_polls_with_3_second_interval(self, content: str) -> None:
        """LiveLog polling interval must be 3000 ms."""
        assert "3000" in content, (
            "LiveLog must configure usePolling with a 3000 ms interval"
        )

    def test_live_log_uses_ref_for_auto_scroll(self, content: str) -> None:
        """LiveLog must use useRef for scroll container to auto-scroll to bottom."""
        assert re.search(r"useRef|scrollIntoView|scrollTop|scrollHeight", content), (
            "LiveLog must use useRef/scrollIntoView or similar for auto-scrolling"
        )

    def test_live_log_uses_effect_for_scroll(self, content: str) -> None:
        """LiveLog must use useEffect to trigger auto-scroll on new entries."""
        assert "useEffect" in content, (
            "LiveLog must use useEffect to auto-scroll when entries change"
        )

    def test_live_log_color_codes_by_event_type(self, content: str) -> None:
        """LiveLog must apply different Tailwind classes based on event type."""
        # Must have some conditional class logic, not a single static class for all
        has_conditional_color = bool(
            re.search(
                r"(switch|===|EventType\.|agent_started|agent_completed|error|ERROR|"
                r"test_passed|test_failed)\s*[^;]*\s*(text-|bg-)",
                content,
            )
            or re.search(
                r"(text-|bg-)(red|green|blue|yellow|gray)\S*.*EventType|"
                r"EventType.*\n.*(text-|bg-)",
                content,
            )
            or (
                re.search(r"EventType\.", content)
                and re.search(r"text-(red|green|blue|yellow)", content)
            )
        )
        assert has_conditional_color, (
            "LiveLog must color-code log entries based on event type "
            "(different colors for error/success/info events)"
        )

    def test_live_log_shows_timestamp(self, content: str) -> None:
        """LiveLog entries must display a timestamp."""
        assert re.search(r"timestamp|\.timestamp", content), (
            "LiveLog entries must display the event timestamp"
        )

    def test_live_log_shows_event_type(self, content: str) -> None:
        """LiveLog entries must display the event type."""
        # Matches entry.type, entry.event_type, log.type, event_type, etc.
        assert re.search(
            r"entry\.(event_)?type|log\.(event_)?type|event_type", content
        ), (
            "LiveLog entries must display the event type (entry.type or entry.event_type)"
        )

    def test_live_log_shows_message_or_details(self, content: str) -> None:
        """LiveLog entries must display the event message/details."""
        assert re.search(r"\.message|\.details|event\.message", content), (
            "LiveLog entries must display event message or details"
        )

    def test_live_log_imports_use_polling(self, content: str) -> None:
        """LiveLog must import usePolling from hooks."""
        assert re.search(
            r"from\s+['\"].*hooks.*usePolling|from\s+['\"].*usePolling", content
        ), "LiveLog must import usePolling from hooks/usePolling"

    def test_live_log_handles_empty_state(self, content: str) -> None:
        """LiveLog must handle empty events (no hardcoded 'Waiting for events...' as the only branch)."""
        # The stub only ever shows "Waiting for events..." — a real implementation
        # conditionally shows it OR maps over real events.
        has_mapping = bool(re.search(r"\.(map|forEach)\s*\(", content))
        assert has_mapping, (
            "LiveLog must map over events to render entries, not just show a static placeholder"
        )


# ===========================================================================
# JobHistory
# ===========================================================================


class TestJobHistory:
    """JobHistory shows a table of recent jobs with status badges and duration."""

    @pytest.fixture()
    def content(self) -> str:
        return read_component("JobHistory.tsx")

    def test_job_history_accepts_jobs_prop(self, content: str) -> None:
        """JobHistory must accept a `jobs` prop (array of JobSummary)."""
        assert re.search(r"jobs\s*[:\?]", content), (
            "JobHistory must accept a 'jobs' prop"
        )

    def test_job_history_accepts_on_select_prop(self, content: str) -> None:
        """JobHistory must accept an onSelect/onJobSelect callback prop."""
        assert re.search(r"onSelect|onJobSelect|onJobClick|selectedJobId", content), (
            "JobHistory must accept an onSelect/onJobSelect callback prop"
        )

    def test_job_history_renders_job_rows(self, content: str) -> None:
        """JobHistory must map over jobs to render table rows."""
        assert re.search(r"jobs\.(map|forEach)\s*\(", content), (
            "JobHistory must map over jobs array to render <tr> rows"
        )

    def test_job_history_shows_status_badge(self, content: str) -> None:
        """JobHistory rows must include a status badge."""
        has_badge = bool(
            re.search(r"status|badge|pending|running|completed|failed", content)
        ) and bool(
            re.search(r"(text-|bg-|border-)(red|green|blue|yellow|gray)", content)
        )
        assert has_badge, (
            "JobHistory must render status badges with color-coded Tailwind classes"
        )

    def test_job_history_shows_duration(self, content: str) -> None:
        """JobHistory must display job duration."""
        assert re.search(r"duration|elapsed|started_at|completed_at", content), (
            "JobHistory must display job duration (started_at/completed_at or computed)"
        )

    def test_job_history_shows_repo_name(self, content: str) -> None:
        """JobHistory must display the repo name or issue number."""
        assert re.search(r"repo|issue_number|issue\.number|issueNumber", content), (
            "JobHistory must display repo name or issue number"
        )

    def test_job_history_row_click_triggers_selection(self, content: str) -> None:
        """Clicking a row must call the selection callback."""
        assert re.search(r"onClick|onSelect|onJobSelect", content), (
            "JobHistory rows must have onClick handlers to trigger job selection"
        )

    def test_job_history_highlights_selected_row(self, content: str) -> None:
        """Selected row must be visually highlighted (different Tailwind class)."""
        has_selected_style = bool(
            re.search(
                r"selectedJobId|selected.*Id|activeJob|isSelected|selectedId", content
            )
        ) and bool(re.search(r"bg-(?:blue|gray|indigo|sky|slate)-[0-9]", content))
        assert has_selected_style, (
            "JobHistory must highlight the selected row with a distinct Tailwind class"
        )

    def test_job_history_imports_job_summary_type(self, content: str) -> None:
        """JobHistory must import JobSummary from types."""
        assert re.search(r"JobSummary|from\s+['\"].*types", content), (
            "JobHistory must import JobSummary from types"
        )


# ===========================================================================
# usePolling hook
# ===========================================================================


class TestUsePollingHook:
    """usePolling custom hook abstracts polling logic with data/loading/error."""

    @pytest.fixture()
    def content(self) -> str:
        return read_hook("usePolling.ts")

    def test_use_polling_file_exists(self) -> None:
        """src/hooks/usePolling.ts must exist."""
        assert (SRC / "hooks" / "usePolling.ts").is_file(), (
            "src/hooks/usePolling.ts does not exist"
        )

    def test_use_polling_is_exported(self, content: str) -> None:
        """usePolling must be exported from the hooks file."""
        assert re.search(
            r"export\s+(default\s+)?function\s+usePolling|export\s*\{.*usePolling",
            content,
        ), (
            "usePolling must be exported (export function usePolling or export { usePolling })"
        )

    def test_use_polling_accepts_fetcher_argument(self, content: str) -> None:
        """usePolling must accept a fetcher function as first argument."""
        assert re.search(
            r"fetcher|fetchFn|fn\s*[:\(]|callback|fetch\s*[:\(]", content
        ), "usePolling must accept a fetcher/fetchFn argument"

    def test_use_polling_accepts_interval_argument(self, content: str) -> None:
        """usePolling must accept an interval argument (ms)."""
        assert re.search(r"interval|delay|ms\s*[:\?=]|intervalMs", content), (
            "usePolling must accept an interval argument"
        )

    def test_use_polling_returns_data(self, content: str) -> None:
        """usePolling must return a `data` field."""
        assert re.search(r"\bdata\b", content), "usePolling must return a 'data' field"

    def test_use_polling_returns_loading(self, content: str) -> None:
        """usePolling must return a `loading` field."""
        assert re.search(r"\bloading\b", content), (
            "usePolling must return a 'loading' field"
        )

    def test_use_polling_returns_error(self, content: str) -> None:
        """usePolling must return an `error` field."""
        assert re.search(r"\berror\b", content), (
            "usePolling must return an 'error' field"
        )

    def test_use_polling_uses_set_interval(self, content: str) -> None:
        """usePolling must use setInterval for periodic polling."""
        assert "setInterval" in content, (
            "usePolling must use setInterval to schedule periodic polling"
        )

    def test_use_polling_clears_interval_on_cleanup(self, content: str) -> None:
        """usePolling must clear the interval on cleanup (no memory leaks)."""
        assert "clearInterval" in content, (
            "usePolling must call clearInterval in useEffect cleanup to prevent leaks"
        )

    def test_use_polling_uses_use_state(self, content: str) -> None:
        """usePolling must use useState to manage data/loading/error state."""
        assert "useState" in content, (
            "usePolling must use useState for state management"
        )

    def test_use_polling_uses_use_effect(self, content: str) -> None:
        """usePolling must use useEffect to manage the polling lifecycle."""
        assert "useEffect" in content, (
            "usePolling must use useEffect to set up and tear down the interval"
        )

    def test_use_polling_uses_use_callback_or_ref(self, content: str) -> None:
        """usePolling must stabilize the fetcher ref to avoid infinite re-renders."""
        assert re.search(r"useCallback|useRef", content), (
            "usePolling should use useCallback or useRef to stabilize the fetcher "
            "reference and avoid infinite re-render loops"
        )


# ===========================================================================
# App.tsx wiring & layout
# ===========================================================================


class TestAppWiring:
    """App.tsx wires all components, manages selectedJobId state, and passes props."""

    @pytest.fixture()
    def content(self) -> str:
        return read_component("App.tsx")

    def test_app_manages_selected_job_id_state(self, content: str) -> None:
        """App.tsx must manage selectedJobId with useState."""
        assert re.search(r"selectedJobId|selectedJob\b", content), (
            "App.tsx must manage selectedJobId state"
        )
        assert "useState" in content, (
            "App.tsx must use useState to manage selectedJobId"
        )

    def test_app_passes_selected_job_to_agent_cards(self, content: str) -> None:
        """App.tsx must pass selectedJobId (or derived events) to AgentCards."""
        # Must have AgentCards with at least one prop passed
        assert re.search(r"<AgentCards\s+[a-zA-Z]", content), (
            "App.tsx must pass props (jobId/events) to AgentCards"
        )

    def test_app_passes_selected_job_to_task_progress(self, content: str) -> None:
        """App.tsx must pass selectedJobId (or derived data) to TaskProgress."""
        assert re.search(r"<TaskProgress\s+[a-zA-Z]", content), (
            "App.tsx must pass props to TaskProgress"
        )

    def test_app_passes_selected_job_to_live_log(self, content: str) -> None:
        """App.tsx must pass selectedJobId to LiveLog."""
        assert re.search(r"<LiveLog\s+[a-zA-Z]", content), (
            "App.tsx must pass props (jobId) to LiveLog"
        )

    def test_app_passes_on_select_to_job_history(self, content: str) -> None:
        """App.tsx must pass an onSelect handler to JobHistory."""
        assert re.search(r"<JobHistory\s+[a-zA-Z]", content), (
            "App.tsx must pass props (onSelect/jobs) to JobHistory"
        )

    def test_app_fetches_jobs_list(self, content: str) -> None:
        """App.tsx must fetch the jobs list (getJobs or usePolling)."""
        has_jobs_fetch = bool(re.search(r"getJobs|usePolling|fetchJobs", content))
        assert has_jobs_fetch, (
            "App.tsx must fetch the jobs list via getJobs or usePolling"
        )

    def test_app_agent_cards_at_top(self, content: str) -> None:
        """AgentCards must appear before TaskProgress and LiveLog in the JSX."""
        agent_pos = content.find("AgentCards")
        task_pos = content.find("TaskProgress")
        live_pos = content.find("LiveLog")
        assert agent_pos != -1 and task_pos != -1 and live_pos != -1, (
            "App.tsx must include AgentCards, TaskProgress, and LiveLog"
        )
        assert agent_pos < task_pos and agent_pos < live_pos, (
            "AgentCards must appear before TaskProgress and LiveLog (top row)"
        )

    def test_app_task_progress_and_live_log_side_by_side(self, content: str) -> None:
        """TaskProgress and LiveLog must be in the same grid/flex container."""
        # They must be siblings inside a div with grid or flex
        assert re.search(
            r"(grid|flex).*\n.*TaskProgress.*\n.*LiveLog|"
            r"TaskProgress.*LiveLog|grid-cols",
            content,
        ), (
            "TaskProgress and LiveLog should be in the same grid/flex container "
            "(side-by-side layout)"
        )

    def test_app_job_history_at_bottom(self, content: str) -> None:
        """JobHistory must appear after AgentCards, TaskProgress, and LiveLog."""
        agent_pos = content.find("AgentCards")
        history_pos = content.find("JobHistory")
        assert agent_pos != -1 and history_pos != -1
        assert history_pos > agent_pos, (
            "JobHistory must appear after AgentCards (bottom of layout)"
        )


# ===========================================================================
# TypeScript build
# ===========================================================================


class TestTypeScriptBuild:
    """npm run build must succeed with no TypeScript errors."""

    def test_npm_build_succeeds(self) -> None:
        """Running `npm run build` in dashboard/frontend must exit 0."""
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"npm run build failed (exit {result.returncode}).\n"
            f"STDOUT:\n{result.stdout[-3000:]}\n"
            f"STDERR:\n{result.stderr[-3000:]}"
        )

    def test_no_typescript_errors_in_tsc(self) -> None:
        """Running tsc --noEmit must produce no TypeScript errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(FRONTEND_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"TypeScript type-check failed.\n"
            f"STDOUT:\n{result.stdout[-3000:]}\n"
            f"STDERR:\n{result.stderr[-3000:]}"
        )
