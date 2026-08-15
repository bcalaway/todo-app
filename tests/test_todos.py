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


def test_create_todo_with_category(client):
    category_id = client.post("/api/categories", json={"name": "Errands"}).json()["id"]

    response = client.post("/api/todos", json={"title": "Buy milk", "category_id": category_id})
    assert response.status_code == 201
    todo = response.json()
    assert todo["category_id"] == category_id
    assert todo["category"]["name"] == "Errands"


def test_set_and_clear_todo_category(client):
    category_id = client.post("/api/categories", json={"name": "Work"}).json()["id"]
    todo_id = client.post("/api/todos", json={"title": "Ship it"}).json()["id"]

    response = client.patch(f"/api/todos/{todo_id}", json={"category_id": category_id})
    assert response.status_code == 200
    assert response.json()["category_id"] == category_id

    # Explicit null must clear it -- distinct from omitting the field
    # entirely, which leaves the existing category untouched.
    response = client.patch(f"/api/todos/{todo_id}", json={"category_id": None})
    assert response.status_code == 200
    assert response.json()["category_id"] is None
