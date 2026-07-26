import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base


@pytest.fixture()
def client():
    # Fresh in-memory SQLite per test -- exercises the real CRUD/ORM code
    # path (not just the "DB unconfigured" degradation covered in
    # test_main.py) without needing a live Postgres instance.
    # StaticPool is required, not optional, for an in-memory SQLite DB used
    # across threads (FastAPI's TestClient runs sync endpoints in a
    # threadpool) -- without it each connection checkout gets its own
    # empty :memory: database, and create_all()'s tables "disappear".
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_and_list_todo(client):
    response = client.post("/api/todos", json={"title": "Buy milk"})
    assert response.status_code == 201
    todo = response.json()
    assert todo["title"] == "Buy milk"
    assert todo["completed"] is False

    response = client.get("/api/todos")
    assert response.status_code == 200
    assert any(t["title"] == "Buy milk" for t in response.json())


def test_update_todo_completed(client):
    todo_id = client.post("/api/todos", json={"title": "Walk dog"}).json()["id"]

    response = client.patch(f"/api/todos/{todo_id}", json={"completed": True})
    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_update_todo_title(client):
    todo_id = client.post("/api/todos", json={"title": "Wlak dog"}).json()["id"]

    response = client.patch(f"/api/todos/{todo_id}", json={"title": "Walk dog"})
    assert response.status_code == 200
    assert response.json()["title"] == "Walk dog"


def test_delete_todo(client):
    todo_id = client.post("/api/todos", json={"title": "Temp"}).json()["id"]

    response = client.delete(f"/api/todos/{todo_id}")
    assert response.status_code == 204

    remaining = client.get("/api/todos").json()
    assert all(t["id"] != todo_id for t in remaining)


def test_update_nonexistent_todo_404(client):
    assert client.patch("/api/todos/999999", json={"completed": True}).status_code == 404


def test_delete_nonexistent_todo_404(client):
    assert client.delete("/api/todos/999999").status_code == 404
