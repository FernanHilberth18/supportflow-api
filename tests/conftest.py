import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

TEST_DB = Path(__file__).parent.parent / "supportflow-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str = "client@example.com") -> dict[str, str]:
    payload = {"email": email, "full_name": "Cliente Demo", "password": "Password123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_staff(role: UserRole = UserRole.AGENT) -> User:
    with TestingSession() as db:
        user = User(
            email=f"{role.value}@example.com",
            full_name=f"Demo {role.value}",
            hashed_password=hash_password("Password123"),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def login_staff(client: TestClient, role: UserRole = UserRole.AGENT) -> dict[str, str]:
    create_staff(role)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"{role.value}@example.com", "password": "Password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
