from fastapi.testclient import TestClient

from app.models import UserRole
from tests.conftest import create_staff, login_staff


def test_register_login_and_me(client: TestClient) -> None:
    payload = {"email": "ana@example.com", "full_name": "Ana Pérez", "password": "Password123"}
    created = client.post("/api/v1/auth/register", json=payload)
    assert created.status_code == 201
    assert created.json()["role"] == "customer"

    login = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["email"] == payload["email"]


def test_duplicate_email_and_invalid_password(client: TestClient) -> None:
    payload = {"email": "ana@example.com", "full_name": "Ana Pérez", "password": "Password123"}
    client.post("/api/v1/auth/register", json=payload)
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": payload["email"], "password": "incorrecta"}
        ).status_code
        == 401
    )


def test_only_admin_can_change_role(client: TestClient) -> None:
    agent_headers = login_staff(client)
    target = create_staff(UserRole.ADMIN)
    assert (
        client.patch(
            f"/api/v1/users/{target.id}/role", json={"role": "agent"}, headers=agent_headers
        ).status_code
        == 403
    )

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    response = client.patch(
        f"/api/v1/users/{target.id}/role", json={"role": "agent"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "agent"
