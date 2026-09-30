# todo-app

A small TODO list app, running on the [home platform](https://github.com/bcalaway/nyc_pa_aws_gitops) — the first app deployed through it, validating the platform's Postgres/Authentik/Traefik/CI-CD framework end-to-end (not just the app itself). See [docs/app-platform.md](https://github.com/bcalaway/nyc_pa_aws_gitops/blob/main/docs/app-platform.md) in that repo for what each integration point means and how onboarding actually works — this repo just implements the contract, it doesn't re-explain it.

Scaffolded from the platform's [Python starter template](https://github.com/bcalaway/nyc_pa_aws_gitops/tree/main/templates/python).

## Stack

FastAPI + Uvicorn, SQLAlchemy (Postgres), Authlib (Authentik OIDC), a single static HTML+JS page (no frontend framework — not needed for this app), pytest, ruff.

## What it does

A todo list: add, list, check off, and delete items, backed by a dedicated Postgres database (`todo-app`). `GET /`, `PATCH /api/todos/{id}` etc. — see `app/main.py`.

## Local development

```
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

`POSTGRES_PASSWORD` / `AUTHENTIK_CLIENT_ID` / `AUTHENTIK_CLIENT_SECRET` are all optional locally — without them the app degrades gracefully (503 on `/api/todos`, 501 on `/login`) instead of requiring live Postgres/Authentik to run.

## Tests and lint

```
pytest
ruff check app/ tests/
```

`tests/test_main.py` covers the platform integration points (health, root, degraded-mode behavior). `tests/test_todos.py` exercises the real CRUD logic against an in-memory SQLite database (`StaticPool`, since SQLite's default per-connection `:memory:` behavior doesn't survive FastAPI's threadpool otherwise) so the ORM logic is verified without needing a live Postgres instance.

Both lint and test also run inside Docker via the `lint` / `test` build stages (`docker build --target lint .` / `--target test .`), which is what `app-ci.yml` runs in CI on every PR.

## Running tests locally

CI uses Python 3.12 (see the `python:3.12-slim` base image in the `Dockerfile`), so use that version if you can. From the repo root, install the runtime and dev dependencies (`requirements-dev.txt` provides `pytest` and `ruff`), then run the tests and the linter the same way CI does:

```
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check app/ tests/
```

No Postgres or Authentik is needed; the tests use an in-memory SQLite database. To run exactly what CI runs, use `docker build --target test .` and `docker build --target lint .`.

## Deploy

Merges to `main` trigger `.github/workflows/cd.yml`: build and push to ECR (`app-build-push.yml`), then deploy to the hub (`app-deploy.yml`) — auto-deploy, no manual promote step. Live at `https://todo-app.billandjessie.com`, behind Authentik login.
Updated by Claude on September 30, 2026.
