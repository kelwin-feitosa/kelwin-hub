"""Kelwin Hub 10: real API, relationships, date grouping and no duplicate actions."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from hub.workspace import _group, LOCAL_TZ


def test_workspace_requires_authentication(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app = create_app(str(tmp_path / 'empty.db'), password_hash=hash_password('valid-local-password-2026'),
                     session_secret='S' * 48, scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/workspace').status_code == 401


def test_contextual_flow_and_existing_data(ctx):
    client, headers, store = ctx
    project = client.post('/api/projects', headers=headers,
                          json={'name': 'Projeto pesquisa', 'area': 'Estudos'}).json()['id']
    contact = client.post('/api/contacts', headers=headers,
                          json={'name': 'Pessoa fictícia'}).json()['id']
    opportunity = client.post('/api/opportunities', headers=headers,
        json={'title': 'Proposta musical', 'next_action': 'Enviar amostra', 'contact_id': contact}).json()['id']
    today = datetime.now(LOCAL_TZ)
    task = client.post('/api/tasks', headers=headers,
        json={'title': 'Preparar amostra', 'project_id': project, 'opportunity_id': opportunity,
              'priority': 2, 'due_at': (today + timedelta(hours=2)).isoformat()})
    assert task.status_code == 201, task.text
    task_id = task.json()['id']
    workspace = client.get('/api/workspace').json()
    items = [x for row in workspace['groups'].values() for x in row]
    assert len(items) == 1, 'A oportunidade com tarefa aberta não deve duplicar a próxima ação'
    assert items[0]['kind'] == 'task'
    assert items[0]['id'] == task_id
    assert items[0]['project_name'] == 'Projeto pesquisa'
    assert items[0]['opportunity_title'] == 'Proposta musical'
    assert items[0]['contact_name'] == 'Pessoa fictícia'
    assert workspace['total_actions'] == 1
    assert client.get('/api/dashboard').status_code == 200
    assert client.patch('/api/tasks/' + task_id, headers=headers, json={'status': 'done'}).status_code == 200
    items = [x for row in client.get('/api/workspace').json()['groups'].values() for x in row]
    assert len(items) == 1 and items[0]['kind'] == 'opportunity'
    assert items[0]['next_action'] == 'Enviar amostra'
    assert len(client.get('/api/tasks').json()) == 1
    assert len(client.get('/api/opportunities').json()) == 1


def test_workspace_preserves_blocked_and_event_confirmation(ctx):
    client, headers, _ = ctx
    task = client.post('/api/tasks', headers=headers, json={'title': 'Aguardando aprovação'}).json()['id']
    assert client.patch('/api/tasks/' + task, headers=headers, json={'status': 'blocked'}).status_code == 200
    now = datetime.now(LOCAL_TZ)
    start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    response = client.post('/api/events', headers=headers,
        json={'title': 'Reunião proposta', 'start_at': start.isoformat(),
              'end_at': end.isoformat(), 'status': 'proposed'})
    assert response.status_code == 201, response.text
    payload = client.get('/api/workspace').json()
    assert payload['groups']['blocked'][0]['title'] == 'Aguardando aprovação'
    assert payload['events'][0]['status'] == 'proposed'


def test_local_grouping_utc_offset_and_priority():
    today = datetime(2026, 11, 11, tzinfo=LOCAL_TZ).date()
    assert _group('2026-11-11T02:30:00+00:00', 1, today=today) == 'now'  # 10 Nov in São Paulo
    assert _group('2026-11-14T18:00:00+00:00', 1, today=today) == 'next'
    assert _group('2026-12-14T18:00:00+00:00', 1, today=today) == 'later'
    assert _group(None, 1, today=today) == 'next'
    assert _group(None, 3, today=today) == 'now'
