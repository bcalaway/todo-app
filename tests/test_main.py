from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Todo" in response.text


def test_categories_page():
    response = client.get("/categories")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Categories" in response.text


def test_db_check_without_configured_db():
    # No POSTGRES_PASSWORD in the test environment -- confirms the app
    # degrades gracefully instead of crashing when Postgres isn't wired up.
    response = client.get("/db-check")
    assert response.status_code == 200
    assert response.json() == {"connected": False}


def test_todos_without_configured_db():
    # Same degradation contract as /db-check -- a clean 503, not a crash,
    # when Postgres isn't wired up (see the real CRUD behavior tests in
    # tests/test_todos.py, which override the DB dependency).
    assert client.get("/api/todos").status_code == 503
    assert client.post("/api/todos", json={"title": "x"}).status_code == 503
    assert client.get("/api/categories").status_code == 503
    assert client.post("/api/categories", json={"name": "x"}).status_code == 503


def test_login_without_configured_auth():
    # No AUTHENTIK_CLIENT_ID/SECRET in the test environment -- confirms the
    # auth routes respond cleanly instead of crashing when Authentik isn't
    # wired up yet.
    response = client.get("/login")
    assert response.status_code == 501
