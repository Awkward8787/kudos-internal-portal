from tests.conftest import auth_headers


def test_html_login_and_give_kudos_form(client):
    token = client.get("/login").get_data(as_text=True)
    assert 'name="csrf_token"' in token

    client.get("/login")
    csrf = client.get("/api/csrf").get_json()["csrf_token"]
    response = client.post(
        "/login",
        data={"username": "priya", "password": "kudos-demo", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    page = client.get("/give")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Jordan Lee (jordan)" in html
    assert "Priya Shah (priya)" not in html
    assert "Give kudos" in html


def test_admin_nav_only_for_administrators(client):
    auth_headers(client, "jordan")
    employee_home = client.get("/").get_data(as_text=True)
    assert ">Admin<" not in employee_home

    auth_headers(client, "admin")
    admin_home = client.get("/").get_data(as_text=True)
    assert ">Admin<" in admin_home
    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "Moderate kudos" in admin_page.get_data(as_text=True)
