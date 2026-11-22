"""Regression for valid ISO timestamps that overflow during UTC conversion."""
import pytest
from fastapi import HTTPException
from hub.api import timestamp


@pytest.mark.parametrize('value',[
    '9999-12-31T23:59:59',
    '9999-12-31T23:59:59-12:00',
    '0001-01-01T00:00:00+14:00',
])
def test_extreme_utc_timestamps_rejected_with_422(value):
    with pytest.raises(HTTPException) as error:
        timestamp(value)
    assert error.value.status_code == 422


@pytest.mark.parametrize(('original','utc'),[
    ('2026-11-21T10:00:00','2026-11-21T13:00:00+00:00'),
    ('2026-11-21T10:00:00Z','2026-11-21T10:00:00+00:00'),
    ('2026-11-21T10:00:00+02:00','2026-11-21T08:00:00+00:00'),
])
def test_normal_timestamps_unchanged(original,utc):
    assert timestamp(original)==utc


@pytest.mark.parametrize('bad',[
    '9999-12-31T23:59:59',
    '0001-01-01T00:00:00+14:00',
])
def test_event_creation_rejects_overflow_without_writing(ctx,bad):
    client,headers,store=ctx
    response=client.post('/api/events',headers=headers,json={
        'title':'Evento de teste nos limites do calendário',
        'start_at':bad,'end_at':'2027-01-01T13:00:00Z',
    })
    assert response.status_code==422,response.text
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE title='Evento de teste nos limites do calendário'").fetchone()[0]==0
