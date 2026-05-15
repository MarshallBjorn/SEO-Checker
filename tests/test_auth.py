def test_register_creates_session(client, unique_email):
    r = client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})
    assert r.status_code == 201
    assert r.json()["email"] == unique_email
    assert "session_id" in client.cookies


def test_login_logout_flow(client, unique_email):
    client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})

    r = client.post("/auth/logout")
    assert r.status_code == 200

    r = client.get("/auth/me")
    assert r.status_code == 403

    r = client.post("/auth/login", data={"email": unique_email, "password": "Test1234!"})
    assert r.status_code == 200

    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == unique_email


def test_login_wrong_password(client, unique_email):
    client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})
    client.post("/auth/logout")
    r = client.post("/auth/login", data={"email": unique_email, "password": "wrong-password"})
    assert r.status_code == 401


def test_register_duplicate_email(client, unique_email):
    client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})
    r = client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})
    assert r.status_code == 409


def test_register_password_too_short(client, unique_email):
    r = client.post("/auth/register", data={"email": unique_email, "password": "short"})
    assert r.status_code == 400
