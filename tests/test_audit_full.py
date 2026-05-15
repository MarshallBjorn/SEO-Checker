def test_audit_requires_login(client):
    r = client.post("/audits", json={"url": "http://1.1.1.1/"})
    assert r.status_code == 403


def test_create_audit_returns_pending(client, unique_email):
    client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})

    r = client.post("/audits", json={"url": "http://1.1.1.1/"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["url"] == "http://1.1.1.1/"
    audit_id = body["id"]

    r = client.get(f"/audits/{audit_id}")
    assert r.status_code == 200
    assert r.json()["id"] == audit_id


def test_create_audit_with_custom_settings(client, unique_email):
    client.post("/auth/register", data={"email": unique_email, "password": "Test1234!"})

    r = client.post(
        "/audits",
        json={
            "url": "http://1.1.1.1/",
            "settings": {
                "weight_meta": 30,
                "enable_headings": False,
                "timeout_ms": 20000,
            },
        },
    )
    assert r.status_code == 201
    audit_id = r.json()["id"]

    r = client.get(f"/audits/{audit_id}")
    settings = r.json()["settings"]
    assert settings["weight_meta"] == 30
    assert settings["enable_headings"] is False
    assert settings["timeout_ms"] == 20000


def test_cannot_access_other_users_audit(client, unique_email):
    # user A tworzy audyt
    email_a = unique_email
    client.post("/auth/register", data={"email": email_a, "password": "Test1234!"})
    r = client.post("/audits", json={"url": "http://1.1.1.1/"})
    audit_id = r.json()["id"]
    client.post("/auth/logout")

    # user B próbuje go odczytać
    import uuid

    email_b = f"other-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", data={"email": email_b, "password": "Test1234!"})
    r = client.get(f"/audits/{audit_id}")
    assert r.status_code == 403
