"""Tests for dashboard/frontend/ React + Vite + TypeScript + Tailwind scaffold."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "dashboard" / "frontend"


class TestPackageJson:
    """dashboard/frontend/package.json exists with required dependencies."""

    @pytest.fixture()
    def pkg(self) -> dict:  # type: ignore[type-arg]
        path = FRONTEND_ROOT / "package.json"
        assert path.is_file(), "dashboard/frontend/package.json does not exist"
        return json.loads(path.read_text())

    def test_package_json_exists(self) -> None:
        """dashboard/frontend/package.json must exist."""
        assert (FRONTEND_ROOT / "package.json").is_file()

    def test_react_in_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include react in dependencies."""
        deps = pkg.get("dependencies", {})
        assert "react" in deps, "react not found in dependencies"

    def test_react_dom_in_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include react-dom in dependencies."""
        deps = pkg.get("dependencies", {})
        assert "react-dom" in deps, "react-dom not found in dependencies"

    def test_typescript_in_dev_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include typescript in devDependencies."""
        dev_deps = pkg.get("devDependencies", {})
        assert "typescript" in dev_deps, "typescript not found in devDependencies"

    def test_tailwindcss_in_dev_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include tailwindcss in devDependencies."""
        dev_deps = pkg.get("devDependencies", {})
        assert "tailwindcss" in dev_deps, "tailwindcss not found in devDependencies"

    def test_vite_in_dev_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include vite in devDependencies."""
        dev_deps = pkg.get("devDependencies", {})
        assert "vite" in dev_deps, "vite not found in devDependencies"

    def test_vite_plugin_react_in_dev_dependencies(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json must include @vitejs/plugin-react in devDependencies."""
        dev_deps = pkg.get("devDependencies", {})
        assert "@vitejs/plugin-react" in dev_deps, (
            "@vitejs/plugin-react not found in devDependencies"
        )

    def test_dev_script_exists(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json scripts must include a 'dev' script."""
        scripts = pkg.get("scripts", {})
        assert "dev" in scripts, "'dev' script not found in package.json scripts"

    def test_build_script_exists(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """package.json scripts must include a 'build' script."""
        scripts = pkg.get("scripts", {})
        assert "build" in scripts, "'build' script not found in package.json scripts"

    def test_build_script_runs_tsc_and_vite(self, pkg: dict) -> None:  # type: ignore[type-arg]
        """The 'build' script must run tsc and vite build."""
        build = pkg.get("scripts", {}).get("build", "")
        assert "tsc" in build, "build script must invoke tsc"
        assert "vite build" in build, "build script must invoke vite build"


class TestTsconfig:
    """dashboard/frontend/tsconfig.json is configured for strict TypeScript."""

    @pytest.fixture()
    def tsconfig(self) -> dict:  # type: ignore[type-arg]
        path = FRONTEND_ROOT / "tsconfig.json"
        assert path.is_file(), "dashboard/frontend/tsconfig.json does not exist"
        return json.loads(path.read_text())

    def test_tsconfig_exists(self) -> None:
        """dashboard/frontend/tsconfig.json must exist."""
        assert (FRONTEND_ROOT / "tsconfig.json").is_file()

    def test_strict_mode_enabled(self, tsconfig: dict) -> None:  # type: ignore[type-arg]
        """tsconfig.json compilerOptions.strict must be true."""
        compiler_opts = tsconfig.get("compilerOptions", {})
        assert compiler_opts.get("strict") is True, (
            "tsconfig.json compilerOptions.strict must be true"
        )

    def test_no_emit_enabled(self, tsconfig: dict) -> None:  # type: ignore[type-arg]
        """tsconfig.json compilerOptions.noEmit must be true (Vite handles emit)."""
        compiler_opts = tsconfig.get("compilerOptions", {})
        assert compiler_opts.get("noEmit") is True, (
            "tsconfig.json compilerOptions.noEmit must be true"
        )

    def test_jsx_set_to_react_jsx(self, tsconfig: dict) -> None:  # type: ignore[type-arg]
        """tsconfig.json compilerOptions.jsx must be 'react-jsx'."""
        compiler_opts = tsconfig.get("compilerOptions", {})
        assert compiler_opts.get("jsx") == "react-jsx", (
            "tsconfig.json compilerOptions.jsx must be 'react-jsx'"
        )

    def test_target_is_es2020(self, tsconfig: dict) -> None:  # type: ignore[type-arg]
        """tsconfig.json compilerOptions.target must be 'ES2020'."""
        compiler_opts = tsconfig.get("compilerOptions", {})
        assert compiler_opts.get("target") == "ES2020", (
            "tsconfig.json compilerOptions.target must be 'ES2020'"
        )

    def test_module_resolution_is_bundler(self, tsconfig: dict) -> None:  # type: ignore[type-arg]
        """tsconfig.json compilerOptions.moduleResolution must be 'bundler'."""
        compiler_opts = tsconfig.get("compilerOptions", {})
        assert compiler_opts.get("moduleResolution") == "bundler", (
            "tsconfig.json compilerOptions.moduleResolution must be 'bundler'"
        )


class TestTailwindConfig:
    """Tailwind CSS is configured with dark mode."""

    def test_tailwind_config_exists(self) -> None:
        """dashboard/frontend/tailwind.config.ts must exist."""
        assert (FRONTEND_ROOT / "tailwind.config.ts").is_file(), (
            "dashboard/frontend/tailwind.config.ts does not exist"
        )

    def test_tailwind_dark_mode_configured(self) -> None:
        """tailwind.config.ts must configure darkMode."""
        content = (FRONTEND_ROOT / "tailwind.config.ts").read_text()
        assert "darkMode" in content, "tailwind.config.ts must define darkMode setting"

    def test_tailwind_content_paths_include_src(self) -> None:
        """tailwind.config.ts content paths must cover src/**/*.{ts,tsx}."""
        content = (FRONTEND_ROOT / "tailwind.config.ts").read_text()
        assert "src" in content, "tailwind.config.ts content paths must include src/"

    def test_postcss_config_exists(self) -> None:
        """dashboard/frontend/postcss.config.cjs must exist."""
        assert (FRONTEND_ROOT / "postcss.config.cjs").is_file(), (
            "dashboard/frontend/postcss.config.cjs does not exist"
        )

    def test_postcss_includes_tailwindcss(self) -> None:
        """postcss.config.cjs must include tailwindcss plugin."""
        content = (FRONTEND_ROOT / "postcss.config.cjs").read_text()
        assert "tailwindcss" in content, "postcss.config.cjs must reference tailwindcss"

    def test_postcss_includes_autoprefixer(self) -> None:
        """postcss.config.cjs must include autoprefixer plugin."""
        content = (FRONTEND_ROOT / "postcss.config.cjs").read_text()
        assert "autoprefixer" in content, (
            "postcss.config.cjs must reference autoprefixer"
        )


class TestAppTsx:
    """App.tsx renders a dark-themed shell with the correct header."""

    def test_app_tsx_exists(self) -> None:
        """dashboard/frontend/src/components/App.tsx must exist."""
        assert (FRONTEND_ROOT / "src" / "components" / "App.tsx").is_file(), (
            "dashboard/frontend/src/components/App.tsx does not exist"
        )

    def test_app_tsx_contains_mission_control_header(self) -> None:
        """The dark-themed shell must render 'Dark Factory — Mission Control'.

        App.tsx may delegate the title to a Header component; in that case
        Header.tsx must contain the literal text.
        """
        app_content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        header_path = FRONTEND_ROOT / "src" / "components" / "Header.tsx"

        # Accept: title in App.tsx directly, OR App uses <Header /> and Header.tsx
        # has it
        if "Dark Factory" in app_content and "Mission Control" in app_content:
            return  # title is inline in App.tsx

        assert "<Header" in app_content or "Header(" in app_content, (
            "App.tsx must either contain 'Dark Factory — Mission Control' directly "
            "or render a <Header /> component"
        )
        assert header_path.is_file(), (
            "App.tsx delegates header to Header component but Header.tsx does not exist"
        )
        header_content = header_path.read_text()
        assert "Dark Factory" in header_content, (
            "Header.tsx must contain 'Dark Factory' text"
        )
        assert "Mission Control" in header_content, (
            "Header.tsx must contain 'Mission Control' text"
        )

    def test_app_tsx_uses_dark_tailwind_classes(self) -> None:
        """App.tsx must use Tailwind dark-mode or dark background classes."""
        content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        # Accept any standard Tailwind dark background shade (800-950)
        has_dark_bg = any(
            cls in content
            for cls in [
                "bg-gray-800",
                "bg-gray-900",
                "bg-gray-950",
                "bg-zinc-800",
                "bg-zinc-900",
                "bg-zinc-950",
                "bg-slate-800",
                "bg-slate-900",
                "bg-slate-950",
                "bg-neutral-800",
                "bg-neutral-900",
                "bg-neutral-950",
                "dark:",
            ]
        )
        assert has_dark_bg, (
            "App.tsx must use Tailwind dark-mode or dark background classes "
            "(e.g. bg-gray-900, bg-gray-950, dark:)"
        )

    def test_app_tsx_has_agent_cards_section(self) -> None:
        """App.tsx must include an AgentCards placeholder section."""
        content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        assert "AgentCards" in content, (
            "App.tsx must include AgentCards component or placeholder"
        )

    def test_app_tsx_has_task_progress_section(self) -> None:
        """App.tsx must include a TaskProgress placeholder section."""
        content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        assert "TaskProgress" in content, (
            "App.tsx must include TaskProgress component or placeholder"
        )

    def test_app_tsx_has_live_log_section(self) -> None:
        """App.tsx must include a LiveLog placeholder section."""
        content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        assert "LiveLog" in content, (
            "App.tsx must include LiveLog component or placeholder"
        )

    def test_app_tsx_has_job_selector(self) -> None:
        """App.tsx must include a job selector (dropdown or JobHistory)."""
        content = (FRONTEND_ROOT / "src" / "components" / "App.tsx").read_text()
        assert "JobHistory" in content or "select" in content, (
            "App.tsx must include a job selector (JobHistory or <select>)"
        )

    def test_main_tsx_entry_point_exists(self) -> None:
        """dashboard/frontend/src/main.tsx must exist as the React entry point."""
        assert (FRONTEND_ROOT / "src" / "main.tsx").is_file(), (
            "dashboard/frontend/src/main.tsx does not exist"
        )

    def test_index_html_exists(self) -> None:
        """dashboard/frontend/index.html must exist as the Vite HTML template."""
        assert (FRONTEND_ROOT / "index.html").is_file(), (
            "dashboard/frontend/index.html does not exist"
        )


class TestDirectoryStructure:
    """dashboard/frontend/ has the correct src/ subdirectory structure."""

    def test_src_components_dir_exists(self) -> None:
        """dashboard/frontend/src/components/ must exist."""
        assert (FRONTEND_ROOT / "src" / "components").is_dir()

    def test_src_hooks_dir_exists(self) -> None:
        """dashboard/frontend/src/hooks/ must exist."""
        assert (FRONTEND_ROOT / "src" / "hooks").is_dir()

    def test_src_types_dir_exists(self) -> None:
        """dashboard/frontend/src/types/ must exist."""
        assert (FRONTEND_ROOT / "src" / "types").is_dir()

    def test_src_api_dir_exists(self) -> None:
        """dashboard/frontend/src/api/ must exist."""
        assert (FRONTEND_ROOT / "src" / "api").is_dir()


class TestTypesIndex:
    """src/types/index.ts defines the required TypeScript interfaces."""

    @pytest.fixture()
    def types_content(self) -> str:
        path = FRONTEND_ROOT / "src" / "types" / "index.ts"
        assert path.is_file(), "dashboard/frontend/src/types/index.ts does not exist"
        return path.read_text()

    def test_types_index_exists(self) -> None:
        """dashboard/frontend/src/types/index.ts must exist."""
        assert (FRONTEND_ROOT / "src" / "types" / "index.ts").is_file()

    def test_event_type_enum_defined(self, types_content: str) -> None:
        """src/types/index.ts must define EventType enum."""
        assert "EventType" in types_content, "src/types/index.ts must define EventType"

    def test_event_type_has_agent_started(self, types_content: str) -> None:
        """EventType must include AGENT_STARTED value."""
        assert "agent_started" in types_content or "AGENT_STARTED" in types_content, (
            "EventType must include AGENT_STARTED = 'agent_started'"
        )

    def test_event_type_has_log_output(self, types_content: str) -> None:
        """EventType must include LOG_OUTPUT value."""
        assert "log_output" in types_content or "LOG_OUTPUT" in types_content, (
            "EventType must include LOG_OUTPUT = 'log_output'"
        )

    def test_event_interface_defined(self, types_content: str) -> None:
        """src/types/index.ts must define Event interface."""
        assert re.search(r"interface\s+Event\b", types_content), (
            "src/types/index.ts must define 'interface Event'"
        )

    def test_event_interface_has_id_field(self, types_content: str) -> None:
        """Event interface must have an id field."""
        # Look for id: string inside an Event block — simple presence check
        assert "id:" in types_content, "Event interface must include 'id' field"

    def test_event_interface_has_timestamp_field(self, types_content: str) -> None:
        """Event interface must have a timestamp field."""
        assert "timestamp" in types_content, (
            "Event interface must include 'timestamp' field"
        )

    def test_event_interface_has_type_field(self, types_content: str) -> None:
        """Event interface must have a type: EventType field."""
        assert "type" in types_content and "EventType" in types_content, (
            "Event interface must include 'type: EventType' field"
        )

    def test_event_interface_has_message_field(self, types_content: str) -> None:
        """Event interface must have a message field."""
        assert "message" in types_content, (
            "Event interface must include 'message' field"
        )

    def test_job_summary_interface_defined(self, types_content: str) -> None:
        """src/types/index.ts must define JobSummary interface."""
        assert re.search(r"interface\s+JobSummary\b", types_content), (
            "src/types/index.ts must define 'interface JobSummary'"
        )

    def test_job_summary_has_issue_number(self, types_content: str) -> None:
        """JobSummary must have an issue_number field."""
        assert "issue_number" in types_content, (
            "JobSummary must include 'issue_number' field"
        )

    def test_job_summary_has_status_field(self, types_content: str) -> None:
        """JobSummary must have a status field with expected union values."""
        assert "status" in types_content, "JobSummary must include 'status' field"
        assert "pending" in types_content and "running" in types_content, (
            "JobSummary status must include 'pending' and 'running' literal types"
        )

    def test_job_summary_has_progress_percent(self, types_content: str) -> None:
        """JobSummary must have a progress_percent field."""
        assert "progress_percent" in types_content, (
            "JobSummary must include 'progress_percent' field"
        )

    def test_job_detail_interface_defined(self, types_content: str) -> None:
        """src/types/index.ts must define JobDetail interface extending JobSummary."""
        assert re.search(r"interface\s+JobDetail\b", types_content), (
            "src/types/index.ts must define 'interface JobDetail'"
        )

    def test_job_detail_extends_job_summary(self, types_content: str) -> None:
        """JobDetail must extend JobSummary."""
        assert re.search(r"JobDetail\s+extends\s+JobSummary", types_content), (
            "JobDetail must extend JobSummary"
        )

    def test_job_detail_has_events_field(self, types_content: str) -> None:
        """JobDetail must have an events: Event[] field."""
        assert "events" in types_content, "JobDetail must include 'events' field"

    def test_job_detail_has_description_field(self, types_content: str) -> None:
        """JobDetail must have a description field."""
        assert "description" in types_content, (
            "JobDetail must include 'description' field"
        )


class TestApiClient:
    """src/api/client.ts defines typed fetch functions for all API endpoints."""

    @pytest.fixture()
    def client_content(self) -> str:
        path = FRONTEND_ROOT / "src" / "api" / "client.ts"
        assert path.is_file(), "dashboard/frontend/src/api/client.ts does not exist"
        return path.read_text()

    def test_client_ts_exists(self) -> None:
        """dashboard/frontend/src/api/client.ts must exist."""
        assert (FRONTEND_ROOT / "src" / "api" / "client.ts").is_file()

    def test_get_jobs_function_defined(self, client_content: str) -> None:
        """client.ts must define a getJobs function."""
        pattern = r"(export\s+)?(async\s+)?function\s+getJobs|getJobs\s*="
        assert re.search(pattern, client_content), (
            "client.ts must define a getJobs function"
        )

    def test_get_jobs_calls_api_v1_jobs(self, client_content: str) -> None:
        """getJobs must target the /api/v1/jobs endpoint.

        Accepts both a hardcoded literal ('/api/v1/jobs') and the common
        pattern of a BASE_URL constant ('/api/v1') combined with '/jobs'.
        """
        uses_literal = "/api/v1/jobs" in client_content
        uses_base_url = "/api/v1" in client_content and (
            '"/jobs"' in client_content
            or "'/jobs'" in client_content
            or "`${" in client_content
            and "/jobs" in client_content
        )
        assert uses_literal or uses_base_url, (
            "client.ts getJobs must target /api/v1/jobs "
            "(either as a literal or via a BASE_URL constant)"
        )

    def test_get_job_function_defined(self, client_content: str) -> None:
        """client.ts must define a getJob function."""
        pattern = r"(export\s+)?(async\s+)?function\s+getJob\b|getJob\s*="
        assert re.search(pattern, client_content), (
            "client.ts must define a getJob function"
        )

    def test_get_job_returns_job_detail(self, client_content: str) -> None:
        """getJob must return a JobDetail type."""
        assert "JobDetail" in client_content, (
            "client.ts must reference JobDetail type in getJob"
        )

    def test_get_job_log_function_defined(self, client_content: str) -> None:
        """client.ts must define a getJobLog function."""
        pattern = r"(export\s+)?(async\s+)?function\s+getJobLog\b|getJobLog\s*="
        assert re.search(pattern, client_content), (
            "client.ts must define a getJobLog function"
        )

    def test_get_job_log_calls_log_endpoint(self, client_content: str) -> None:
        """getJobLog must fetch from /api/v1/jobs/{id}/log."""
        assert "/log" in client_content, (
            "client.ts must reference the /log endpoint for getJobLog"
        )

    def test_imports_from_types(self, client_content: str) -> None:
        """client.ts must import types from ../types or ../types/index."""
        assert re.search(r"from\s+['\"]\.\.\/types", client_content), (
            "client.ts must import from ../types"
        )

    def test_job_summary_type_used(self, client_content: str) -> None:
        """client.ts must reference JobSummary type."""
        assert "JobSummary" in client_content, (
            "client.ts must reference JobSummary type"
        )


class TestViteConfig:
    """Vite dev server proxies /api to localhost:8420."""

    @pytest.fixture()
    def vite_config_content(self) -> str:
        path = FRONTEND_ROOT / "vite.config.ts"
        assert path.is_file(), "dashboard/frontend/vite.config.ts does not exist"
        return path.read_text()

    def test_vite_config_exists(self) -> None:
        """dashboard/frontend/vite.config.ts must exist."""
        assert (FRONTEND_ROOT / "vite.config.ts").is_file()

    def test_vite_config_has_proxy(self, vite_config_content: str) -> None:
        """vite.config.ts must define a proxy configuration."""
        assert "proxy" in vite_config_content, (
            "vite.config.ts must define a proxy configuration"
        )

    def test_vite_config_proxies_api_to_localhost_8420(
        self, vite_config_content: str
    ) -> None:
        """vite.config.ts proxy must route /api to localhost:8420."""
        assert "localhost:8420" in vite_config_content, (
            "vite.config.ts proxy must target http://localhost:8420"
        )
        assert "/api" in vite_config_content, (
            "vite.config.ts proxy must match /api path"
        )

    def test_vite_config_uses_react_plugin(self, vite_config_content: str) -> None:
        """vite.config.ts must use the @vitejs/plugin-react plugin."""
        assert (
            "plugin-react" in vite_config_content or "react()" in vite_config_content
        ), "vite.config.ts must import and use @vitejs/plugin-react"


class TestFrontendMakefile:
    """dashboard/frontend/Makefile has install, dev, build, clean targets."""

    @pytest.fixture()
    def makefile_content(self) -> str:
        path = FRONTEND_ROOT / "Makefile"
        assert path.is_file(), "dashboard/frontend/Makefile does not exist"
        return path.read_text()

    def test_makefile_exists(self) -> None:
        """dashboard/frontend/Makefile must exist."""
        assert (FRONTEND_ROOT / "Makefile").is_file()

    def test_install_target_exists(self, makefile_content: str) -> None:
        """Makefile must have an 'install:' target."""
        assert re.search(r"^install:", makefile_content, re.MULTILINE), (
            "'install:' target not found in dashboard/frontend/Makefile"
        )

    def test_dev_target_exists(self, makefile_content: str) -> None:
        """Makefile must have a 'dev:' target."""
        assert re.search(r"^dev:", makefile_content, re.MULTILINE), (
            "'dev:' target not found in dashboard/frontend/Makefile"
        )

    def test_build_target_exists(self, makefile_content: str) -> None:
        """Makefile must have a 'build:' target."""
        assert re.search(r"^build:", makefile_content, re.MULTILINE), (
            "'build:' target not found in dashboard/frontend/Makefile"
        )

    def test_clean_target_exists(self, makefile_content: str) -> None:
        """Makefile must have a 'clean:' target."""
        assert re.search(r"^clean:", makefile_content, re.MULTILINE), (
            "'clean:' target not found in dashboard/frontend/Makefile"
        )

    def test_phony_targets_declared(self, makefile_content: str) -> None:
        """Makefile must declare .PHONY for the standard targets."""
        assert ".PHONY" in makefile_content, (
            "dashboard/frontend/Makefile must declare .PHONY targets"
        )

    def test_install_target_runs_npm(self, makefile_content: str) -> None:
        """install target must run npm install or npm ci."""
        match = re.search(
            r"^install:.*\n((?:\t.+\n?)*)", makefile_content, re.MULTILINE
        )
        assert match, "install: target not found"
        body = match.group(1)
        assert "npm" in body, "install target must invoke npm"

    def test_build_target_runs_npm_run_build(self, makefile_content: str) -> None:
        """build target must run npm run build."""
        match = re.search(r"^build:.*\n((?:\t.+\n?)*)", makefile_content, re.MULTILINE)
        assert match, "build: target not found"
        body = match.group(1)
        assert "npm" in body and "build" in body, (
            "build target must invoke npm run build"
        )
