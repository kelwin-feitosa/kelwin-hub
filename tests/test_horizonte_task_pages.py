"""Bounded task pagination, literal text search and backwards compatibility."""
import pytest


def create_task(client, headers, title):
    response = client.post('/api/tasks', headers=headers, json={'title': title})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_task_pages_are_bounded_stable_and_non_overlapping(ctx):
    client, headers, _ = ctx
    created = {create_task(client, headers, 'Tarefa fictícia ' + str(index)) for index in range(38)}
    first = client.get('/api/tasks/page?limit=30&offset=0').json()
    second = client.get('/api/tasks/page?limit=30&offset=30').json()
    assert first['total'] == second['total'] == 38
    assert len(first['items']) == 30
    assert len(second['items']) == 8
    assert first['has_more'] is True
    assert second['has_more'] is False
    ids = {x['id'] for x in first['items'] + second['items']}
    assert ids == created
    assert len(client.get('/api/tasks').json()) == 38  # legacy list contract


def test_task_status_filters_and_literal_search(ctx):
    client, headers, _ = ctx
    a = create_task(client, headers, 'Reunião 100% confirmada')
    b = create_task(client, headers, 'Reunião 100x confirmada')
    c = create_task(client, headers, 'Plano único')
    assert client.patch('/api/tasks/' + b, headers=headers,
                        json={'status': 'blocked'}).status_code == 200
    assert client.patch('/api/tasks/' + c, headers=headers,
                        json={'status': 'done'}).status_code == 200
    open_page = client.get('/api/tasks/page?status=open').json()
    assert [x['id'] for x in open_page['items']] == [a]
    blocked_page = client.get('/api/tasks/page?status=blocked').json()
    assert [x['id'] for x in blocked_page['items']] == [b]
    done_page = client.get('/api/tasks/page?status=done').json()
    assert [x['id'] for x in done_page['items']] == [c]
    literal = client.get('/api/tasks/page', params={'q': '100%'}).json()
    assert [x['id'] for x in literal['items']] == [a]
    wildcard = client.get('/api/tasks/page', params={'q': '_'}).json()
    assert wildcard['total'] == 0
    injection = client.get('/api/tasks/page', params={'q': "' OR 1=1 --"}).json()
    assert injection['total'] == 0


@pytest.mark.parametrize('params', [
    {'limit': 0}, {'limit': 101}, {'offset': -1},
    {'offset': 1000001}, {'status': 'unknown'}, {'q': 'x' * 101},
])
def test_task_page_rejects_invalid_parameters(ctx, params):
    client, _, _ = ctx
    response = client.get('/api/tasks/page', params=params)
    assert response.status_code == 422, response.text


def test_task_page_rejects_unauthenticated_requests(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app = create_app(str(tmp_path/'temp.db'),
                     password_hash=hash_password('Senha-fictícia-segura-2026'),
                     session_secret='S' * 48, scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/tasks/page').status_code == 401
