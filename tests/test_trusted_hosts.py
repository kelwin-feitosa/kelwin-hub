"""Local-first Host header protection including Compose and TestClient."""
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password


def test_local_hosts_are_allowed_but_untrusted_hosts_are_rejected(tmp_path):
    password = 'Senha-Ficticia-FORJA-2026!'
    app = create_app(
        str(tmp_path / 'guard.db'),
        password_hash=hash_password(password),
        session_secret='local-test-' * 5,
        scheduler=False,
    )
    with TestClient(app) as client:
        for host in ('testserver', '127.0.0.1:8000', 'localhost:8000', 'hub:8000'):
            response = client.get('/healthz', headers={'Host': host})
            assert response.status_code == 200, (host, response.text)
        for host in ('attacker.invalid', 'other.example:8000', 'localhost.attacker.invalid'):
            response = client.get('/healthz', headers={'Host': host})
            assert response.status_code == 400, (host, response.text)
            response = client.post('/api/login', headers={'Host': host},
                                   json={'password': password})
            assert response.status_code == 400
        # Login still works locally; CSRF/Origin checks are unchanged.
        login = client.post('/api/login', headers={'Host': 'localhost:8000'},
                            json={'password': password})
        assert login.status_code == 200
