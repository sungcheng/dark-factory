"""Project scaffolding — create new repos ready for the factory."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from factory.github_client import GitHubClient
from factory.security import generate_security_policy
from factory.templates import apply_template

LOG = logging.getLogger(__name__)

CI_PYTHON = """\
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/
      - run: uv run pytest tests/ -v --tb=short

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .
"""

CI_TERRAFORM = """\
name: Terraform CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9"
      - run: terraform fmt -check -recursive
      - run: terraform init -backend=false
      - run: terraform validate

  plan:
    needs: validate
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9"
      - run: terraform init -backend=false
      - run: terraform plan -var-file=environments/staging/terraform.tfvars -no-color
"""

CI_FULLSTACK = """\
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/
      - run: uv run pytest tests/ -v --tb=short

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm run build
"""

CI_WORKFLOWS: dict[str | None, str] = {
    None: CI_PYTHON,
    "fastapi": CI_PYTHON,
    "fullstack": CI_FULLSTACK,
    "terraform": CI_TERRAFORM,
}


def create_project(
    name: str,
    template: str | None = None,
    public: bool = False,
    description: str = "",
) -> str:
    """Create a new project repo, optionally with a template.

    Without --template: creates a bare repo with CLAUDE.md, CI/CD,
    and README. The Architect scaffolds the project based on the
    first issue.

    With --template: also applies the specified scaffold.

    Returns the repo URL.
    """
    github = GitHubClient()

    # Step 1: Create the GitHub repo
    LOG.info("Creating repo: %s (public=%s)", name, public)
    repo = github._gh.get_user().create_repo(  # type: ignore[union-attr]
        name=name,
        description=description or "Built by Dark Factory",
        private=not public,
        auto_init=True,
    )
    repo_url = repo.html_url
    LOG.info("Created: %s", repo_url)

    # Step 2: Clone it locally
    with tempfile.TemporaryDirectory(prefix="df-scaffold-") as tmp:
        clone_url = f"https://{github.token}@github.com/{github.owner}/{name}.git"
        subprocess.run(
            ["git", "clone", clone_url, tmp],
            capture_output=True,
            check=True,
        )

        # Step 3: Apply template (if specified)
        if template:
            LOG.info("Applying template: %s", template)
            apply_template(
                template,
                tmp,
                variables={"PROJECT_NAME": name},
            )

        # Step 4: Write CLAUDE.md
        _write_claude_md(Path(tmp), name, template)

        # Step 5: Write CI/CD workflow
        ci_dir = Path(tmp) / ".github" / "workflows"
        ci_dir.mkdir(parents=True, exist_ok=True)
        ci_content = CI_WORKFLOWS.get(template, CI_PYTHON)
        (ci_dir / "ci.yml").write_text(ci_content)

        # Step 6: Write README
        _write_readme(Path(tmp), name, description, template)

        # Step 7: Commit and push
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp,
            capture_output=True,
        )
        tmpl_msg = f" from {template} template" if template else ""
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"feat: initialize {name}{tmpl_msg}\n\nGenerated by Dark Factory",
            ],
            cwd=tmp,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            LOG.error("Push failed: %s", result.stderr)
            raise RuntimeError(f"Failed to push: {result.stderr}")

    LOG.info("Project %s ready at %s", name, repo_url)
    return repo_url


def _write_claude_md(
    target: Path,
    name: str,
    template: str | None,
) -> None:
    """Write CLAUDE.md with project-appropriate rules."""
    security = generate_security_policy()

    if template == "fullstack":
        content = (
            f"# CLAUDE.md\n\n"
            f"Project: {name} (Fullstack)\n\n"
            f"## Structure\n\n"
            f"- `backend/` — FastAPI API\n"
            f"- `frontend/` — React + Vite + Tailwind\n\n"
            f"## Build & Test\n\n"
            f"```bash\n"
            f"make develop    # Install backend + frontend deps\n"
            f"make test       # Run backend tests\n"
            f"make check      # Lint backend\n"
            f"make staging    # Docker Compose (localhost:8001 + :3001)\n"
            f"```\n\n"
            f"## Rules\n\n"
            f"- Backend APIs under `/api/v1/`\n"
            f"- Frontend proxies `/api` to backend\n"
            f"- Tests required for all backend features\n"
            f"- No secrets in code\n"
            f"- Type hints on all Python functions\n\n"
            f"{security}\n"
        )
    elif template == "terraform":
        content = (
            f"# CLAUDE.md\n\n"
            f"Project: {name} (Terraform)\n\n"
            f"## Build & Test\n\n"
            f"```bash\n"
            f"make init       # Initialize Terraform\n"
            f"make plan       # Plan changes (ENV=staging)\n"
            f"make apply      # Apply changes (ENV=staging)\n"
            f"make check      # fmt check + validate + lint\n"
            f"make fmt        # Auto-format .tf files\n"
            f"```\n\n"
            f"## Rules\n\n"
            f"- All resources must be tagged with Project, "
            f"Environment, ManagedBy\n"
            f"- Use modules for reusable components\n"
            f"- Use variables — no hardcoded values\n"
            f"- Use terraform.tfvars per environment\n"
            f"- No secrets in .tf files — use variables "
            f"or AWS Secrets Manager\n"
            f"- Always run `terraform fmt` before committing\n"
            f"- Always run `terraform validate` before "
            f"pushing\n\n"
            f"{security}\n"
        )
    else:
        content = (
            f"# CLAUDE.md\n\n"
            f"Project: {name}\n\n"
            f"## Build & Test\n\n"
            f"```bash\n"
            f"make develop    # Install deps\n"
            f"make test       # Run tests\n"
            f"make check      # Lint + types\n"
            f"make format     # Auto-format\n"
            f"```\n\n"
            f"## Rules\n\n"
            f"- All APIs under `/api/v1/`\n"
            f"- Tests required for all features\n"
            f"- No secrets in code\n"
            f"- Type hints on all functions\n\n"
            f"{security}\n"
        )

    (target / "CLAUDE.md").write_text(content)


def _write_readme(
    target: Path,
    name: str,
    description: str,
    template: str | None,
) -> None:
    """Write a README appropriate for the project type."""
    desc = description or "Built by Dark Factory."

    if template == "fullstack":
        content = (
            f"# {name}\n\n"
            f"{desc}\n\n"
            f"## Setup\n\n"
            f"```bash\n"
            f"make develop    # install all deps\n"
            f"```\n\n"
            f"## Development\n\n"
            f"```bash\n"
            f"# Backend\n"
            f"cd backend && make test\n\n"
            f"# Frontend\n"
            f"cd frontend && npm run dev   # http://localhost:5173\n"
            f"```\n\n"
            f"## Deploy\n\n"
            f"```bash\n"
            f"make staging       # backend :8001, frontend :3001\n"
            f"make prod          # backend :8000, frontend :3000\n"
            f"make staging-down  # stop staging\n"
            f"make prod-down     # stop production\n"
            f"```\n"
        )
    elif template == "terraform":
        content = (
            f"# {name}\n\n"
            f"{desc}\n\n"
            f"## Prerequisites\n\n"
            f"- [Terraform](https://terraform.io) >= 1.5\n"
            f"- AWS credentials configured\n"
            f"- [tflint](https://github.com/terraform-linters"
            f"/tflint) (optional)\n\n"
            f"## Usage\n\n"
            f"```bash\n"
            f"make init                    # initialize\n"
            f"make plan ENV=staging        # plan changes\n"
            f"make apply ENV=staging       # apply changes\n"
            f"make plan ENV=production     # plan prod\n"
            f"make apply ENV=production    # apply prod\n"
            f"```\n\n"
            f"## Structure\n\n"
            f"```\n"
            f".\n"
            f"├── main.tf              # Provider + core config\n"
            f"├── variables.tf         # Input variables\n"
            f"├── outputs.tf           # Output values\n"
            f"├── backend.tf           # Remote state config\n"
            f"├── modules/             # Reusable modules\n"
            f"└── environments/\n"
            f"    ├── staging/\n"
            f"    │   └── terraform.tfvars\n"
            f"    └── production/\n"
            f"        └── terraform.tfvars\n"
            f"```\n"
        )
    else:
        content = (
            f"# {name}\n\n"
            f"{desc}\n\n"
            f"## Setup\n\n"
            f"```bash\n"
            f"uv sync --all-extras\n"
            f"```\n\n"
            f"## Development\n\n"
            f"```bash\n"
            f"make develop    # install deps\n"
            f"make test       # run tests\n"
            f"make check      # lint + types\n"
            f"```\n"
        )

    (target / "README.md").write_text(content)
