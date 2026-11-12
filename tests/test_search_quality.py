"""Behavior contracts for the search implementation, independent of its optimization."""


def test_search_indicates_per_kind_truncation(ctx):
    client, csrf, _ = ctx
    for idx in range(14):
        response = client.post('/api/projects', headers=csrf, json={
            'name': f'Forja Pesquisa {idx:02}', 'area': 'pessoal',
        })
        assert response.status_code == 201
    response = client.get('/api/search', params={'q': 'Forja Pesquisa'})
    assert response.status_code == 200
    body = response.json()
    assert len([item for item in body['results'] if item['kind'] == 'projects']) == 8
    assert body['limited'] is True  # Before FORJA: incorrectly False.
