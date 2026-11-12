"""Live authenticated API tests of private schedule availability."""
from datetime import date,timedelta
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password


def test_availability_preview_conflicts_and_privacy(tmp_path):
    app=create_app(str(tmp_path/'db.sqlite'),password_hash=hash_password('Fictional-password-1234'),session_secret='B'*48,scheduler=False)
    c=TestClient(app)
    url='/api/availability/windows'
    assert c.get(url).status_code==401
    c.post('/api/login',json={'password':'Fictional-password-1234'})
    headers={'X-CSRF-Token':c.get('/api/session').json()['csrf']}
    # Wednesday in January 2027, future relative to Nov 2026.
    day='2027-01-06'
    assert date.fromisoformat(day).weekday()==2
    assert c.get('/api/availability/slots',params={'day':day}).json()['slots']==[]
    assert c.post(url,json={'weekday':2,'start_time':'09:00','end_time':'11:00'}).status_code==403
    invalid=c.post(url,headers=headers,json={'weekday':2,'start_time':'11:00','end_time':'09:00'})
    assert invalid.status_code==422
    added=c.post(url,headers=headers,json={'weekday':2,'start_time':'09:00','end_time':'11:00'})
    assert added.status_code==201,added.text
    ident=added.json()['id']
    assert c.post(url,headers=headers,json={'weekday':2,'start_time':'10:30','end_time':'11:30'}).status_code==409
    def slots(**kw):return c.get('/api/availability/slots',params={'day':day,'duration':30,'step':30,**kw}).json()['slots']
    assert [x['local_start'][11:16] for x in slots()]==['09:00','09:30','10:00','10:30']
    confirmed=c.post('/api/events',headers=headers,json={'title':'Reunião fictícia','start_at':day+'T09:30:00-03:00','end_at':day+'T10:00:00-03:00','status':'confirmed'})
    assert confirmed.status_code==201,confirmed.text
    assert [x['local_start'][11:16] for x in slots()]==['09:00','10:00','10:30']
    assert [x['local_start'][11:16] for x in slots(buffer=10)]==['10:30']
    assert c.post('/api/events',headers=headers,json={'title':'Apenas sugestão','start_at':day+'T10:30:00-03:00','end_at':day+'T11:00:00-03:00','status':'proposed'}).status_code==201
    assert len(slots())==3
    assert c.delete(url+'/'+ident).status_code==403
    assert c.delete(url+'/'+ident,headers=headers).status_code==200
    assert slots()==[]
    assert c.get('/api/availability/slots',params={'day':'invalid'}).status_code==422
    assert c.get('/api/availability/slots',params={'day':day,'duration':10000}).status_code==422


def test_local_slot_projection_dedup_and_boundaries():
    from datetime import datetime, timezone
    from hub.availability import calculate_slots
    day=date(2027,1,6)
    windows=[{'start_time':'09:00','end_time':'10:30'}, {'start_time':'09:30','end_time':'11:00'}]
    events=[{'start_at':'2027-01-06T12:30:00+00:00','end_at':'2027-01-06T13:00:00+00:00'}]
    available=calculate_slots(windows,events,day,30,30,0,datetime(2026,11,12,tzinfo=timezone.utc))
    assert [s['local_start'][11:16] for s in available]==['09:00','10:00','10:30']
    assert all(s['start_at'].endswith('+00:00') for s in available)
