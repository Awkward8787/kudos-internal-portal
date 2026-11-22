from datetime import datetime, timedelta, timezone

from app.db import get_db
from tests.conftest import auth_headers, login


def _ids(client):
    login(client, "jordan")
    colleagues = {row["username"]: row["id"] for row in client.get("/api/colleagues").get_json()}
    me = client.get("/api/me").get_json()
    return me, colleagues


def test_colleague_list_excludes_current_user(client):
    me, colleagues = _ids(client)
    assert "jordan" not in colleagues
    assert set(colleagues) == {"admin", "priya", "marcus", "anthony"}
    names = [row["display_name"] for row in client.get("/api/colleagues").get_json()]
    assert names == sorted(names, key=str.lower)


def test_create_kudos_appears_on_feed(client):
    me, colleagues = _ids(client)
    headers = auth_headers(client)
    response = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": "  Thanks for reviewing the notes.  "},
        headers=headers,
    )
    assert response.status_code == 201
    item = response.get_json()
    assert item["message"] == "Thanks for reviewing the notes."
    assert item["from_user"]["username"] == "jordan"
    assert item["to_user"]["username"] == "priya"
    assert item["is_visible"] is True

    feed = client.get("/api/kudos").get_json()
    assert feed["total"] == 1
    assert feed["items"][0]["id"] == item["id"]
    assert feed["items"][0]["message"] == "Thanks for reviewing the notes."


def test_cannot_give_kudos_to_self(client):
    me, _ = _ids(client)
    response = client.post(
        "/api/kudos",
        json={"to_user_id": me["id"], "message": "I am great."},
        headers=auth_headers(client),
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "self_kudos"


def test_empty_and_overlong_messages_are_rejected(client):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    empty = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": "   "},
        headers=headers,
    )
    assert empty.status_code == 400
    assert empty.get_json()["error"] == "invalid_message"

    too_long = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": "x" * 501},
        headers=headers,
    )
    assert too_long.status_code == 400
    assert too_long.get_json()["error"] == "invalid_message"


def test_unknown_recipient_returns_404(client):
    _ids(client)
    response = client.post(
        "/api/kudos",
        json={"to_user_id": 99999, "message": "Hello there."},
        headers=auth_headers(client),
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_invalid_recipient_returns_400(client):
    _ids(client)
    response = client.post(
        "/api/kudos",
        json={"to_user_id": "priya", "message": "Hello there."},
        headers=auth_headers(client),
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_recipient"


def test_duplicate_within_24_hours_is_rejected(client):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    payload = {"to_user_id": colleagues["priya"], "message": "Nice work on the release."}
    first = client.post("/api/kudos", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/kudos", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.get_json()["error"] == "duplicate"

    different = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": "A different note."},
        headers=headers,
    )
    assert different.status_code == 201

    other_person = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["marcus"], "message": "Nice work on the release."},
        headers=headers,
    )
    assert other_person.status_code == 201


def test_same_message_allowed_after_duplicate_window(client, app):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    message = "Same note after the window."
    first = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": message},
        headers=headers,
    )
    assert first.status_code == 201

    old = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(microsecond=0)
    old_stamp = old.strftime("%Y-%m-%dT%H:%M:%SZ")
    with app.app_context():
        get_db().execute(
            "UPDATE kudos SET created_at = ? WHERE id = ?",
            (old_stamp, first.get_json()["id"]),
        )
        get_db().commit()

    again = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["priya"], "message": message},
        headers=headers,
    )
    assert again.status_code == 201


def test_rate_limit_after_ten_kudos_in_an_hour(client):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    for index in range(10):
        response = client.post(
            "/api/kudos",
            json={"to_user_id": colleagues["priya"], "message": f"Thank you number {index}."},
            headers=headers,
        )
        assert response.status_code == 201, response.get_json()

    blocked = client.post(
        "/api/kudos",
        json={"to_user_id": colleagues["marcus"], "message": "One too many."},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "rate_limited"


def test_feed_is_newest_first_and_paginated(client):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    for index in range(3):
        client.post(
            "/api/kudos",
            json={"to_user_id": colleagues["priya"], "message": f"Note {index}."},
            headers=headers,
        )

    page1 = client.get("/api/kudos?page=1&per_page=2").get_json()
    assert page1["total"] == 3
    assert page1["total_pages"] == 2
    assert page1["per_page"] == 2
    assert [item["message"] for item in page1["items"]] == ["Note 2.", "Note 1."]

    page2 = client.get("/api/kudos?page=2&per_page=2").get_json()
    assert [item["message"] for item in page2["items"]] == ["Note 0."]


def test_html_in_message_is_escaped_on_dashboard(client):
    _, colleagues = _ids(client)
    headers = auth_headers(client)
    payload = {"to_user_id": colleagues["priya"], "message": "<script>alert('xss')</script>"}
    created = client.post("/api/kudos", json=payload, headers=headers)
    assert created.status_code == 201

    page = client.get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "<script>alert('xss')</script>" not in html
    assert "&#39;" in html or "&lt;script&gt;" in html
