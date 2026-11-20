import pytest

from app import create_app
from app.db import init_db


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "test.db"),
            "SEED_SAMPLE_KUDOS": False,
            "RATE_LIMIT_PER_HOUR": 10,
            "DUPLICATE_WINDOW_HOURS": 24,
        }
    )
    with app.app_context():
        init_db()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_headers(client):
    response = client.get("/api/csrf")
    token = response.get_json()["csrf_token"]
    return {"X-CSRF-Token": token}


def login(client, username="jordan", password="kudos-demo"):
    return client.post(
        "/api/login",
        json={"username": username, "password": password},
        headers=csrf_headers(client),
    )


def auth_headers(client, username="jordan", password="kudos-demo"):
    login(client, username=username, password=password)
    return csrf_headers(client)
