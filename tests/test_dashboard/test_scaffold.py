"""Tests for dashboard scaffold: package structure, FastAPI app, and config files."""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# Project root is two levels up from this test file
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestPackageStructure:
    """factory/dashboard/ package exists with correct files."""

    def test_dashboard_package_init_exists(self) -> None:
        """factory/dashboard/__init__.py must exist."""
        assert (PROJECT_ROOT / "factory" / "dashboard" / "__init__.py").is_file()

    def test_dashboard_app_exists(self) -> None:
        """factory/dashboard/app.py must exist."""
        assert (PROJECT_ROOT / "factory" / "dashboard" / "app.py").is_file()

    def test_dashboard_models_exists(self) -> None:
        """factory/dashboard/models.py must exist."""
        assert (PROJECT_ROOT / "factory" / "dashboard" / "models.py").is_file()

    def test_dashboard_db_exists(self) -> None:
        """factory/dashboard/db.py must exist."""
        assert (PROJECT_ROOT / "factory" / "dashboard" / "db.py").is_file()

    def test_dashboard_routers_init_exists(self) -> None:
        """factory/dashboard/routers/__init__.py must exist."""
        assert (PROJECT_ROOT / "factory" / "dashboard" / "routers" / "__init__.py").is_file()

    def test_dashboard_frontend_dir_exists(self) -> None:
        """dashboard/frontend/ directory must exist at project root."""
        assert (PROJECT_ROOT / "dashboard" / "frontend").is_dir()

    def test_test_dashboard_init_exists(self) -> None:
        """tests/test_dashboard/__init__.py must exist."""
        assert (PROJECT_ROOT / "tests" / "test_dashboard" / "__init__.py").is_file()


class TestFastAPIApp:
    """factory/dashboard/app.py creates a FastAPI app with /api/v1 prefix."""

    def test_app_is_importable(self) -> None:
        """factory.dashboard.app module must be importable."""
        from factory.dashboard import app as dashboard_app  # noqa: F401

    def test_app_instance_exists(self) -> None:
        """factory.dashboard.app must expose an `app` FastAPI instance."""
        from factory.dashboard.app import app
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_create_app_returns_fastapi(self) -> None:
        """create_app() must return a FastAPI instance."""
        from factory.dashboard.app import create_app
        from fastapi import FastAPI

        result = create_app()
        assert isinstance(result, FastAPI)

    def test_router_prefix_is_api_v1(self) -> None:
        """The app must include a router with /api/v1 prefix."""
        from factory.dashboard.app import app

        # Collect all route prefixes from included routers
        prefixes = [
            route.path
            for route in app.routes
            if hasattr(route, "path")
        ]
        # At minimum the router mount must mean /api/v1 appears in routes
        # (docs/openapi are at root; api routes will be under /api/v1/...)
        # We verify the router was registered by checking that routes
        # outside /docs /openapi still only live under /api/v1.
        non_meta_paths = [
            p for p in prefixes
            if not p.startswith("/docs")
            and not p.startswith("/openapi")
            and not p.startswith("/redoc")
        ]
        # All non-meta routes must start with /api/v1
        for path in non_meta_paths:
            assert path.startswith("/api/v1"), (
                f"Route {path!r} does not start with /api/v1"
            )

    def test_app_responds_via_test_client(self) -> None:
        """TestClient must be able to make requests to the app (requires httpx)."""
        from factory.dashboard.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        # /docs should return 200
        response = client.get("/docs")
        assert response.status_code == 200

    def test_unknown_route_returns_404(self) -> None:
        """Unknown routes must return 404."""
        from factory.dashboard.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == 404

    def test_root_route_not_defined(self) -> None:
        """Root / should not return 200 (no handler registered there)."""
        from factory.dashboard.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 404


class TestPyprojectDependencies:
    """pyproject.toml includes required dashboard dependencies."""

    @pytest.fixture()
    def pyproject_text(self) -> str:
        return (PROJECT_ROOT / "pyproject.toml").read_text()

    def test_fastapi_in_dependencies(self, pyproject_text: str) -> None:
        """pyproject.toml must list fastapi as a dependency."""
        assert re.search(r'^\s*"fastapi', pyproject_text, re.MULTILINE), (
            "fastapi not found in pyproject.toml dependencies"
        )

    def test_uvicorn_standard_in_dependencies(self, pyproject_text: str) -> None:
        """pyproject.toml must list uvicorn[standard] as a dependency."""
        assert re.search(r'^\s*"uvicorn\[standard\]', pyproject_text, re.MULTILINE), (
            "uvicorn[standard] not found in pyproject.toml dependencies"
        )

    def test_aiosqlite_in_dependencies(self, pyproject_text: str) -> None:
        """pyproject.toml must list aiosqlite as a dependency."""
        assert re.search(r'^\s*"aiosqlite', pyproject_text, re.MULTILINE), (
            "aiosqlite not found in pyproject.toml dependencies"
        )

    def test_httpx_in_dev_dependencies(self, pyproject_text: str) -> None:
        """pyproject.toml dev extras must include httpx for TestClient support."""
        assert re.search(r'^\s*"httpx', pyproject_text, re.MULTILINE), (
            "httpx not found in pyproject.toml dev dependencies (required for FastAPI TestClient)"
        )


class TestMakefileTargets:
    """Makefile has dashboard and dashboard-dev targets."""

    @pytest.fixture()
    def makefile_text(self) -> str:
        return (PROJECT_ROOT / "Makefile").read_text()

    def test_dashboard_target_exists(self, makefile_text: str) -> None:
        """Makefile must have a 'dashboard:' target."""
        assert re.search(r"^dashboard:", makefile_text, re.MULTILINE), (
            "'dashboard:' target not found in Makefile"
        )

    def test_dashboard_dev_target_exists(self, makefile_text: str) -> None:
        """Makefile must have a 'dashboard-dev:' target."""
        assert re.search(r"^dashboard-dev:", makefile_text, re.MULTILINE), (
            "'dashboard-dev:' target not found in Makefile"
        )

    def test_dashboard_target_runs_uvicorn(self, makefile_text: str) -> None:
        """dashboard target must invoke uvicorn pointing at factory.dashboard.app:app."""
        # Find the dashboard target block
        match = re.search(
            r"^dashboard:.*\n((?:\t.+\n)*)", makefile_text, re.MULTILINE
        )
        assert match, "dashboard target not found"
        body = match.group(1)
        assert "uvicorn" in body, "dashboard target must run uvicorn"
        assert "factory.dashboard.app:app" in body, (
            "dashboard target must point at factory.dashboard.app:app"
        )

    def test_dashboard_dev_target_has_reload(self, makefile_text: str) -> None:
        """dashboard-dev target must pass --reload to uvicorn."""
        match = re.search(
            r"^dashboard-dev:.*\n((?:\t.+\n)*)", makefile_text, re.MULTILINE
        )
        assert match, "dashboard-dev target not found"
        body = match.group(1)
        assert "--reload" in body, "dashboard-dev target must pass --reload to uvicorn"


class TestEnvExample:
    """`.env.example` includes DASHBOARD_PORT=8420."""

    @pytest.fixture()
    def env_example_text(self) -> str:
        return (PROJECT_ROOT / ".env.example").read_text()

    def test_dashboard_port_present(self, env_example_text: str) -> None:
        """.env.example must define DASHBOARD_PORT."""
        assert re.search(r"^DASHBOARD_PORT=", env_example_text, re.MULTILINE), (
            "DASHBOARD_PORT not found in .env.example"
        )

    def test_dashboard_port_value(self, env_example_text: str) -> None:
        """.env.example must set DASHBOARD_PORT to 8420."""
        assert re.search(r"^DASHBOARD_PORT=8420$", env_example_text, re.MULTILINE), (
            "DASHBOARD_PORT is not set to 8420 in .env.example"
        )
