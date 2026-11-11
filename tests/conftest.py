import pytest
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password

@pytest.fixture
def ctx(tmp_path):
    password='SenhaLocal-Ficticia-2026!'
    app=create_app(str(tmp_path/'hub.db'),password_hash=hash_password(password),session_secret='S'*48,internal_token='internal-token-test-001',scheduler=False)
    with TestClient(app) as client:
        client.post('/api/login',json={'password':password})
        csrf=client.get('/api/session').json()['csrf']
        yield client, {'X-CSRF-Token':csrf}, app.state.store
