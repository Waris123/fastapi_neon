import pytest
from fastapi.testclient import TestClient
from fastapi_neon.main import app, create_db_and_tables

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_teardown_test_db():
    create_db_and_tables()
    yield

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

def test_create_todo():
    todo_data = {"content": "Test Todo"}
    response = client.post("/todos/", json=todo_data)
    assert response.status_code == 200
    assert "id" in response.json()
    assert response.json()["content"] == todo_data["content"]

def test_read_todos():
    response = client.get("/todos/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_todo():

    todo_data = {"content": "Test Todo"}
    create_response = client.post("/todos/", json=todo_data)
    assert create_response.status_code == 200
    created_todo_id = create_response.json()["id"]

    updated_todo_data = {"content": "Updated Todo"}
    response = client.patch(f"/todos/{created_todo_id}", json=updated_todo_data)
    assert response.status_code == 200
    assert response.json()["content"] == updated_todo_data["content"]

def test_delete_todo():

    todo_data = {"content": "Test Todo"}
    create_response = client.post("/todos/", json=todo_data)
    assert create_response.status_code == 200
    created_todo_id = create_response.json()["id"]

    response = client.delete(f"/todos/{created_todo_id}")
    assert response.status_code == 200
    assert response.json() == "Successfully deleted the todo from the Database"

def test_register_user():
    user_data = {"email": "test@example.com", "name": "Test User", "password": "testpassword"}
    response = client.post("/users/register", json=user_data)
    assert response.status_code == 200
    assert isinstance(response.json(), str)

def test_login_user():
    user_data = {"email": "test@example.com", "password": "testpassword"}
    response = client.post("/users/login", json=user_data)
    assert response.status_code == 200
    assert isinstance(response.json(), str)

def test_update_user_info():

    user_data = {"email": "test@example.com", "name": "Test User", "password": "testpassword"}
    register_response = client.post("/users/register", json=user_data)
    assert register_response.status_code == 200

    login_response = client.post("/users/login", json=user_data)
    assert login_response.status_code == 200
    token = login_response.json()

    updated_user_data = {"email": "updated@example.com", "name": "Updated User"}
    response = client.patch("/users/me", json=updated_user_data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == updated_user_data["email"]
    assert response.json()["name"] == updated_user_data["name"]

def test_delete_user():

    user_data = {"email": "test@example.com", "name": "Test User", "password": "testpassword"}
    register_response = client.post("/users/register", json=user_data)
    assert register_response.status_code == 200

    login_response = client.post("/users/login", json=user_data)
    assert login_response.status_code == 200
    token = login_response.json()

    response = client.delete("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"message": "User deleted successfully"}

if __name__ == "__main__":
    pytest.main()
