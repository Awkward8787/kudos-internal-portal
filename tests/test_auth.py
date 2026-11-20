from tests.conftest import auth_headers, csrf_headers, login


def test_login_success(client):
    response = login(client, "Jordan", "kudos-demo")
    assert response.status_code == 200
    body = response.get_json()
    assert body["username"] == "jordan"
    assert body["display_name"] == "Jordan Lee"
    assert body["role"] == "employee"
    assert "password" not in body
    assert "password_hash" not in body


def test_login_failure_is_generic(client):
    missing = login(client, "nobody", "kudos-demo")
    assert missing.status_code == 401
    assert missing.get_json()["message"] == "Incorrect username or password."

    wrong = login(client, "jordan", "wrong-password")
    assert wrong.status_code == 401
    assert wrong.get_json()["message"] == "Incorrect username or password."


def test_login_requires_csrf(client):
    response = client.post("/api/login", json={"username": "jordan", "password": "kudos-demo"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "csrf"


def test_unauthenticated_api_is_rejected(client):
    response = client.get("/api/kudos")
    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthenticated"


def test_unauthenticated_page_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout_clears_session(client):
    headers = auth_headers(client)
    assert client.get("/api/me").status_code == 200
    logout = client.post("/api/logout", headers=headers)
    assert logout.status_code == 204
    assert client.get("/api/me").status_code == 401


def test_me_returns_current_user(client):
    auth_headers(client, "admin")
    body = client.get("/api/me").get_json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
