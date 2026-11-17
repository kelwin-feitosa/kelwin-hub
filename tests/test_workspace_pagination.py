"""H17-01: exact counts, stable bounded Mesa and progressive access to every action."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from hub.api import create_app
from hub.security import hash_password
from hub.workspace import load_workspace, load_workspace_group, LOCAL_TZ


def seed_large_work(store):
    with store.transaction() as db:
        db.execute(
            "INSERT INTO contacts(id,name,company,email,phone,category,source,created_at) "
            "VALUES('contact-x','Contato fictício','','','','business','manual','2026-11-17')")
        db.executemany(
            """INSERT INTO opportunities
               (id,contact_id,title,kind,status,value_cents,next_action,followup_at,
                last_contact_at,created_at,updated_at)
               VALUES(?, 'contact-x', ?, 'test', 'active', 0, 'Responder', NULL,
                      NULL, '2026-11-17', '2026-11-17')""",
            [('opp-solo','Retorno sem tarefa'),('opp-linked','Retorno com tarefa')])
        tasks=[]
        for i in range(150):
            status='open' if i<130 else 'blocked' if i<140 else 'done'
            priority=3 if i<70 else 1
            tasks.append((f'task-{i:03d}',f'Tarefa de ensaio {i:03d}',status,priority,
                          'opp-linked' if i==0 else None))
        db.executemany(
            """INSERT INTO tasks
               (id,title,project_id,opportunity_id,status,priority,due_at,next_action,
                completed_at,created_at) VALUES (?,?,NULL,?,?,?,NULL,'',NULL,'2026-11-17')""",
            tasks)
        now=datetime.now(LOCAL_TZ)
        day=now.replace(hour=10,minute=0,second=0,microsecond=0)
        entries=[
            (f'event-{i:02d}',f'Evento fictício {i}',day.isoformat(),
             (day+timedelta(hours=1)).isoformat())
            for i in range(20)
        ]
        db.executemany(
            """INSERT INTO events(id,title,start_at,end_at,status,source,created_at)
               VALUES(?,?,?,?,'confirmed','local','2026-11-17')""",entries)


def test_bounded_workspace_preserves_counts_and_urgent_sort(ctx):
    client, _, store=ctx
    seed_large_work(store)
    response=client.get('/api/workspace')
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['group_counts']=={'now':70,'next':61,'later':0,'blocked':10}
    assert payload['total_actions']==141
    assert len(payload['groups']['now'])==12
    assert len(payload['groups']['next'])==12
    assert len(payload['groups']['blocked'])==10
    assert payload['groups']['later']==[]
    assert payload['groups']['now'][0]['id']=='task-000'
    assert payload['events_total']==20
    assert len(payload['events'])==12
    assert all(x['kind']=='task' for x in payload['groups']['now'])
    assert not any(x['id']=='opp-linked' for group in payload['groups'].values() for x in group)
    assert 'opp-solo' in {x['id'] for x in payload['groups']['next']}
    assert client.get('/api/workspace?per_group=5').json()['groups']['now'][0]['id']=='task-000'


def test_every_workspace_item_accessible_through_pages(ctx):
    client, _, store=ctx
    seed_large_work(store)
    initial=client.get('/api/workspace').json()
    expected={'now':70,'next':61,'blocked':10,'later':0}
    for group,count in expected.items():
        seen=[]
        for offset in range(0,count,30):
            response=client.get(f'/api/workspace/groups/{group}',
                                params={'offset':offset,'limit':30})
            assert response.status_code==200,response.text
            data=response.json()
            assert data['total']==count
            assert data['offset']==offset
            assert data['group']==group
            assert data['has_more']==(offset+len(data['items'])<count)
            seen.extend(item['id'] for item in data['items'])
        assert len(seen)==len(set(seen))==count
        assert seen[:len(initial['groups'][group])]==[
            item['id'] for item in initial['groups'][group]]


@pytest.mark.parametrize('params',[
    {'per_group':0},{'per_group':51},{'per_group':'abc'}])
def test_workspace_rejects_unbounded_initial_page(ctx,params):
    client, _, _=ctx
    assert client.get('/api/workspace',params=params).status_code==422


@pytest.mark.parametrize(('group','params'),[
    ('now',{'limit':0}),('now',{'limit':101}),('next',{'offset':-1}),
    ('next',{'offset':1000001}),('other',{}),
])
def test_group_paging_validates_input(ctx,group,params):
    client, _, _=ctx
    result=client.get('/api/workspace/groups/'+group,params=params)
    assert result.status_code==422,result.text


def test_group_paging_requires_login(tmp_path):
    app=create_app(str(tmp_path/'empty.db'),
                   password_hash=hash_password('Fictitious-workspace-password'),
                   session_secret='W'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/workspace').status_code==401
        assert client.get('/api/workspace/groups/now').status_code==401


def test_streaming_projection_matches_full_semantics_in_small_dataset(ctx):
    client, _, store=ctx
    seed_large_work(store)
    page=load_workspace(store,per_group=50,events_limit=50)
    assert len(page['events'])==20
    full_now=load_workspace_group(store,'now',offset=0,limit=100)
    assert len(full_now['items'])==70
    assert [r['id'] for r in page['groups']['now']]==[
        r['id'] for r in full_now['items'][:50]]
    assert page['group_counts']['now']==full_now['total']
