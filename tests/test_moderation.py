from tests.conftest import auth_headers, login


def _give_from_jordan(client, message="Thanks for the walkthrough."):
    login(client, "jordan")
    colleagues = {row["username"]: row["id"] for row in client.get("/api/colleagues").get_json()}
    headers = auth_headers(client, "jordan")
    response = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": message},
        headers=headers,
    )
    assert response.status_code == 201
    return response.get_json()["id"]


def test_non_admin_cannot_hide_or_delete(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "jordan")
    hide = client.post(
        f"/api/kudos/{kudos_id}/hide",
        json={"reason": "spam"},
        headers=headers,
    )
    assert hide.status_code == 403
    delete = client.delete(f"/api/kudos/{kudos_id}", headers=headers)
    assert delete.status_code == 403


def test_admin_hide_removes_from_public_feed_but_keeps_admin_list(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "admin")
    hide = client.post(
        f"/api/kudos/{kudos_id}/hide",
        json={"reason": "Inappropriate language."},
        headers=headers,
    )
    assert hide.status_code == 200
    body = hide.get_json()
    assert body["is_visible"] is False
    assert body["reason_for_moderation"] == "Inappropriate language."
    assert body["moderated_by"]["username"] == "admin"
    assert body["moderated_at"]

    public = client.get("/api/kudos").get_json()
    assert public["total"] == 0
    assert public["items"] == []

    admin_list = client.get("/api/admin/kudos").get_json()
    assert admin_list["total"] == 1
    assert admin_list["items"][0]["id"] == kudos_id
    assert admin_list["items"][0]["is_visible"] is False


def test_hide_requires_a_reason(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "admin")
    response = client.post(
        f"/api/kudos/{kudos_id}/hide",
        json={"reason": "  "},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_reason"


def test_admin_restore_returns_kudos_to_the_feed(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "admin")
    client.post(
        f"/api/kudos/{kudos_id}/hide",
        json={"reason": "Needs review."},
        headers=headers,
    )
    restored = client.post(
        f"/api/kudos/{kudos_id}/unhide",
        json={"reason": "Restored after review."},
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.get_json()["is_visible"] is True
    feed = client.get("/api/kudos").get_json()
    assert feed["total"] == 1
    assert feed["items"][0]["id"] == kudos_id


def test_admin_delete_removes_from_both_lists(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "admin")
    deleted = client.delete(f"/api/kudos/{kudos_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/kudos").get_json()["total"] == 0
    assert client.get("/api/admin/kudos").get_json()["total"] == 0


def test_delete_of_hidden_kudos_is_allowed(client):
    kudos_id = _give_from_jordan(client)
    headers = auth_headers(client, "admin")
    client.post(
        f"/api/kudos/{kudos_id}/hide",
        json={"reason": "Spam."},
        headers=headers,
    )
    deleted = client.delete(f"/api/kudos/{kudos_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/admin/kudos").get_json()["total"] == 0


def test_hide_or_delete_missing_kudos_returns_404(client):
    auth_headers(client, "admin")
    headers = auth_headers(client, "admin")
    hide = client.post("/api/kudos/999/hide", json={"reason": "Gone."}, headers=headers)
    assert hide.status_code == 404
    delete = client.delete("/api/kudos/999", headers=headers)
    assert delete.status_code == 404


def test_employee_cannot_open_admin_page(client):
    auth_headers(client, "jordan")
    response = client.get("/admin")
    assert response.status_code == 403
