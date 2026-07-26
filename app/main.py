import pathlib
from contextlib import asynccontextmanager

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import check_connection, create_tables, get_db
from app.models import Todo
from app.schemas import TodoCreate, TodoOut, TodoUpdate

STATIC_DIR = pathlib.Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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


@app.get("/db-check")
def db_check():
    return {"connected": check_connection()}


@app.get("/api/todos", response_model=list[TodoOut])
def list_todos(db: Session = Depends(get_db)):
    return db.query(Todo).order_by(Todo.created_at).all()


@app.post("/api/todos", response_model=TodoOut, status_code=201)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    todo = Todo(title=payload.title)
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
