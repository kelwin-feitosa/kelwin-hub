"""H17-08: bounded raw ASGI bodies (chunked and Content-Length), real HTTP API."""
import asyncio

import pytest
from starlette.responses import JSONResponse

from hub.body_limits import BodyLimitMiddleware, DEFAULT_MAX_BODY, TRANSCRIPT_MAX_BODY, body_budget


def direct_asgi(path,frames,headers=()):
    """Run a synthetic HTTP request without using network or personal data."""
    called={'n':0,'bytes':0}
    sent=[]
    pending=list(frames)
    scope={'type':'http','method':'POST','path':path,
           'headers':list(headers),'asgi':{'version':'3.0'},'http_version':'1.1'}
    async def downstream(scope,receive,send):
        called['n']+=1
        payload=bytearray()
        while True:
            frame=await receive()
            assert frame['type']=='http.request'
            payload.extend(frame.get('body',b''))
            if not frame.get('more_body',False):
                break
        called['bytes']=len(payload)
        await JSONResponse({'received':len(payload)})(scope,receive,send)
    async def receive():
        if pending:
            return pending.pop(0)
        return {'type':'http.disconnect'}
    async def send(message):
        sent.append(message)
    asyncio.run(BodyLimitMiddleware(downstream)(scope,receive,send))
    statuses=[msg['status'] for msg in sent if msg['type']=='http.response.start']
    return statuses[0] if statuses else None,called


def frame(size,more=False):
    return {'type':'http.request','body':b'x'*size,'more_body':more}


def test_content_length_rejected_before_downstream():
    status,called=direct_asgi('/api/projects',[frame(1)],
                               [(b'content-length',str(DEFAULT_MAX_BODY+1).encode())])
    assert status==413 and called['n']==0


@pytest.mark.parametrize('bad',[(b'content-length',b'-1'),(b'content-length',b'unknown')])
def test_invalid_content_length_rejected(bad):
    status,called=direct_asgi('/api/projects',[frame(1)],[bad])
    assert status==400 and called['n']==0


def test_duplicate_content_length_is_not_trusted():
    headers=[(b'content-length',b'2'),(b'content-length',b'1')]
    status,called=direct_asgi('/api/projects',[frame(1)],headers)
    assert status==400 and called['n']==0


def test_chunked_without_content_length_rejects_before_parser():
    frames=[frame(300*1024,True),frame(300*1024)]
    status,called=direct_asgi('/api/projects',frames)
    assert status==413 and called['n']==0


def test_valid_chunked_body_is_replayed_without_loss():
    frames=[frame(6,True),frame(0,True),frame(9)]
    status,called=direct_asgi('/api/projects',frames)
    assert status==200 and called=={'n':1,'bytes':15}


def test_large_transcript_route_has_separate_finite_budget():
    assert body_budget('/api/projects')==DEFAULT_MAX_BODY
    assert body_budget('/api/events/abc/transcripts')==TRANSCRIPT_MAX_BODY
    assert body_budget('/api/meeting-review/transcripts/abc/analyses')==TRANSCRIPT_MAX_BODY
    assert body_budget('/api/meeting-review/items/abc/convert')==DEFAULT_MAX_BODY
    frames=[frame(300*1024,True),frame(300*1024)]
    status,called=direct_asgi('/api/events/abc/transcripts',frames)
    assert status==200 and called=={'n':1,'bytes':600*1024}
    status,called=direct_asgi('/api/meeting-review/items/abc/convert',frames)
    assert status==413 and called['n']==0


def test_synthetic_http_json_is_limited_and_cannot_write(ctx):
    client,headers,_=ctx
    response=client.post('/api/projects',headers=headers,json={'name':'X'*600_000})
    assert response.status_code==413,response.text
    assert client.get('/api/projects').json()==[]
    valid=client.post('/api/projects',headers=headers,
                      json={'name':'Projeto fictício','area':'pessoal'})
    assert valid.status_code==201,valid.text


def test_existing_unicode_transcript_import_still_works(ctx):
    client,headers,_=ctx
    event=client.post('/api/events',headers=headers,json={
        'title':'Reunião local fictícia','start_at':'2027-01-12T10:00',
        'end_at':'2027-01-12T11:00'}).json()['id']
    transcript=client.post(f'/api/events/{event}/transcripts',headers=headers,
        json={'format':'txt','content':'á'*95_000,'source_name':'ficcao.txt'})
    assert transcript.status_code==201,transcript.text
    assert len(client.get('/api/transcripts/'+transcript.json()['id']).json()['content'])==95_000
