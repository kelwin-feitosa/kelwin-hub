"""Security regression for the new navigation; synthetic local-only installation.

Checks are defensive and intentionally complement (not replace) the existing
session, CSRF, backup and TrustedHost regressions.
"""
from fastapi.testclient import TestClient

from hub.api import create_app
from hub.security import hash_password


def test_local_assets_headers_authentication_and_csrf_survive_navigation(tmp_path):
    password = 'Senha-Ficticia-Orbita-2026!'
    app = create_app(
        str(tmp_path / 'private.db'),
        password_hash=hash_password(password),
        session_secret='isolated-session-secret-' * 3,
        scheduler=False,
    )
    with TestClient(app) as client:
        index = client.get('/')
        assert index.status_code == 200
        assert index.headers['Cache-Control'] == 'no-store'
        assert index.headers['X-Frame-Options'] == 'DENY'
        assert index.headers['X-Content-Type-Options'] == 'nosniff'
        csp = index.headers['Content-Security-Policy']
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        for path in ('/static/app.js', '/static/orbita-navigation.js',
                     '/static/orbita-navigation.css'):
            asset = client.get(path)
            assert asset.status_code == 200
            assert asset.headers['X-Content-Type-Options'] == 'nosniff'

        assert client.get('/api/export').status_code == 401
        assert client.get('/api/search?q=teste').status_code == 401
        assert client.post('/api/projects', json={'name': 'x', 'area': 'y'}).status_code == 401
        invalid_host = client.get('/api/session', headers={'Host': 'attacker.example'})
        assert invalid_host.status_code == 400

        login = client.post('/api/login', json={'password': password})
        assert login.status_code == 200
        cookie = login.headers.get('set-cookie', '').lower()
        assert 'httponly' in cookie and 'samesite=strict' in cookie
        token = client.get('/api/session').json()['csrf']
        assert token
        form = {'name': 'Projeto de segurança fictício', 'area': 'Teste'}
        assert client.post('/api/projects', json=form).status_code == 403
        csrf = {'X-CSRF-Token': token}
        assert client.post('/api/projects', json=form,
                           headers={**csrf, 'Origin': 'http://attacker.example'}).status_code == 403
        assert client.post('/api/projects', json=form, headers=csrf).status_code == 200
        assert client.post('/api/logout', headers=csrf).status_code == 200
        assert client.get('/api/export').status_code == 401
