"""Tests for authentication (setup, login, logout, me, route protection)."""


def test_status_unconfigured(app_client):
    response = app_client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_setup_creates_user_and_sets_cookie(app_client):
    response = app_client.post(
        "/api/auth/setup", json={"username": "admin", "password": "secret123"}
    )
    assert response.status_code == 201
    assert response.json() == {"username": "admin"}
    assert "session" in app_client.cookies
    assert app_client.get("/api/auth/status").json() == {"configured": True}


def test_setup_twice_conflicts(app_client):
    app_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    response = app_client.post(
        "/api/auth/setup", json={"username": "other", "password": "secret123"}
    )
    assert response.status_code == 409


def test_setup_password_too_short(app_client):
    response = app_client.post(
        "/api/auth/setup", json={"username": "admin", "password": "123"}
    )
    assert response.status_code == 422


def test_me_requires_auth(app_client):
    response = app_client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_with_session(app_client):
    app_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    response = app_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"username": "admin"}


def test_login_wrong_password(app_client):
    app_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    app_client.cookies.clear()
    response = app_client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrongpass"}
    )
    assert response.status_code == 401
    assert app_client.get("/api/auth/me").status_code == 401


def test_login_success(app_client):
    app_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    app_client.cookies.clear()
    response = app_client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json() == {"username": "admin"}
    assert app_client.get("/api/auth/me").status_code == 200


def test_logout_clears_session(app_client):
    app_client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    response = app_client.post("/api/auth/logout")
    assert response.status_code == 200
    assert app_client.get("/api/auth/me").status_code == 401


def test_protected_route_requires_auth(app_client):
    response = app_client.get("/api/accounts")
    assert response.status_code == 401


def test_protected_route_with_auth(client):
    response = client.get("/api/accounts")
    assert response.status_code == 200
