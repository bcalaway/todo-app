def test_create_and_list_category(client):
    response = client.post("/api/categories", json={"name": "Errands"})
    assert response.status_code == 201
    category = response.json()
    assert category["name"] == "Errands"

    response = client.get("/api/categories")
    assert response.status_code == 200
    assert any(c["name"] == "Errands" for c in response.json())


def test_create_duplicate_category_409(client):
    client.post("/api/categories", json={"name": "Work"})
    response = client.post("/api/categories", json={"name": "Work"})
    assert response.status_code == 409


def test_rename_category(client):
    category_id = client.post("/api/categories", json={"name": "Hom"}).json()["id"]

    response = client.patch(f"/api/categories/{category_id}", json={"name": "Home"})
    assert response.status_code == 200
    assert response.json()["name"] == "Home"


def test_rename_category_to_existing_name_409(client):
    client.post("/api/categories", json={"name": "Errands"})
    category_id = client.post("/api/categories", json={"name": "Work"}).json()["id"]

    response = client.patch(f"/api/categories/{category_id}", json={"name": "Errands"})
    assert response.status_code == 409


def test_delete_category_clears_it_from_todos(client):
    category_id = client.post("/api/categories", json={"name": "Temp"}).json()["id"]
    todo_id = client.post("/api/todos", json={"title": "Buy milk", "category_id": category_id}).json()["id"]

    response = client.delete(f"/api/categories/{category_id}")
    assert response.status_code == 204

    todo = client.get("/api/todos").json()
    todo = next(t for t in todo if t["id"] == todo_id)
    assert todo["category_id"] is None


def test_update_nonexistent_category_404(client):
    assert client.patch("/api/categories/999999", json={"name": "x"}).status_code == 404


def test_delete_nonexistent_category_404(client):
    assert client.delete("/api/categories/999999").status_code == 404
