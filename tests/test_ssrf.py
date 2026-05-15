import uuid

import pytest

from app.middleware.ssrf import is_safe_url


@pytest.mark.parametrize("url", ["http://1.1.1.1/", "https://8.8.8.8/"])
def test_public_ips_allowed(url):
    assert is_safe_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://192.168.1.1/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",  # AWS / OpenStack metadata
        "http://0.0.0.0/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "gopher://example.com/",
    ],
)
def test_unsafe_urls_blocked(url):
    assert is_safe_url(url) is False


def test_ssrf_rejected_at_audit_endpoint(client):
    email = f"ssrf-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", data={"email": email, "password": "Test1234!"})
    r = client.post("/audits", json={"url": "http://169.254.169.254/"})
    assert r.status_code == 400
