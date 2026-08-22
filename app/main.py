import pathlib
from contextlib import asynccontextmanager

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import check_connection, create_tables, get_db
from app.models import Category, Todo
from app.schemas import CategoryCreate, CategoryOut, CategoryUpdate, TodoCreate, TodoOut, TodoUpdate

STATIC_DIR = pathlib.Path(__file__).parent / "static"

# Routes reachable without an authenticated session -- everything else
# (including /static/*, checked separately below) is gated by
# RequireAuthMiddleware.
PUBLIC_PATHS = {"/health", "/login", "/auth/callback"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class RequireAuthMiddleware(BaseHTTPMiddleware):
    # Only enforced once real Authentik credentials are configured -- pre-onboarding
    # (no client id/secret in SSM yet), the app stays open rather than locking itself
    # out before auth is even wired up.
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not _auth_configured or path in PUBLIC_PATHS or path.startswith("/static/"):
            return await call_next(request)
        if not request.session.get("user"):
            if path.startswith("/api/"):
                return JSONResponse({"error": "authentication required"}, status_code=401)
            return RedirectResponse(url="/login")
        return await call_next(request)


# Starlette's add_middleware prepends to the middleware list, so the middleware
# added LAST ends up running FIRST on an incoming request. RequireAuthMiddleware
# reads request.session, so it must run after SessionMiddleware -- meaning
# RequireAuthMiddleware has to be added first, SessionMiddleware second.
app.add_middleware(RequireAuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# Registered only when real credentials are present (post-onboarding, see
# docs/app-platform.md's Auth section in nyc_pa_aws_gitops) -- the
# discovery URL matches Authentik's per-application OIDC endpoint,
# https://auth.billandjessie.com/application/o/<app-slug>/.well-known/openid-configuration.
oauth = OAuth()
_auth_configured = bool(settings.authentik_client_id and settings.authentik_client_secret)
if _auth_configured:
    oauth.register(
        name="authentik",
        client_id=settings.authentik_client_id,
        client_secret=settings.authentik_client_secret,
        server_metadata_url=(
            f"{settings.authentik_base_url}/application/o/{settings.app_name}/"
            ".well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid profile email"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/categories")
def categories_page():
    return FileResponse(STATIC_DIR / "categories.html")


@app.get("/db-check")
def db_check():
    return {"connected": check_connection()}


@app.get("/api/todos", response_model=list[TodoOut])
def list_todos(db: Session = Depends(get_db)):
    return db.query(Todo).order_by(Todo.created_at).all()


@app.post("/api/todos", response_model=TodoOut, status_code=201)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    todo = Todo(title=payload.title, category_id=payload.category_id)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


@app.patch("/api/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, payload: TodoUpdate, db: Session = Depends(get_db)):
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    if payload.title is not None:
        todo.title = payload.title
    if payload.completed is not None:
        todo.completed = payload.completed
    if payload.archived is not None:
        todo.archived = payload.archived
    # Checked via model_fields_set, not "is not None" like the fields above --
    # category_id needs an explicit-null case (clearing a todo's category),
    # which the is-not-None pattern can't distinguish from "not provided".
    if "category_id" in payload.model_fields_set:
        todo.category_id = payload.category_id
    db.commit()
    db.refresh(todo)
    return todo


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(todo)
    db.commit()


@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()


@app.post("/api/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    category = Category(name=payload.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category already exists") from None
    db.refresh(category)
    return category


@app.patch("/api/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if payload.name is not None:
        category.name = payload.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category already exists") from None
    db.refresh(category)
    return category


@app.delete("/api/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    # Explicit application-level unset rather than a DB-level ON DELETE SET
    # NULL -- keeps behavior identical between the SQLite test DB (no FK
    # enforcement) and real Postgres, instead of depending on DB-specific
    # cascade behavior.
    db.query(Todo).filter(Todo.category_id == category_id).update({"category_id": None})
    db.delete(category)
    db.commit()


@app.get("/login")
async def login(request: Request):
    if not _auth_configured:
        return JSONResponse({"error": "auth not configured"}, status_code=501)
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.authentik.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    if not _auth_configured:
        return JSONResponse({"error": "auth not configured"}, status_code=501)
    token = await oauth.authentik.authorize_access_token(request)
    request.session["user"] = token.get("userinfo")
    return RedirectResponse(url="/")
