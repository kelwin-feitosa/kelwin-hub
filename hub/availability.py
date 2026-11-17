"""Local availability preview: never advertises or publishes booking slots externally.

This module is an advisory preview. The confirmed event creation route remains the
atomic booking authority, using BEGIN IMMEDIATE and conflict checks in the Hub.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .storage import Store, new_id, now_utc, rows, record

LOCAL_ZONE=ZoneInfo('America/Sao_Paulo')


def valid_time(s: str) -> bool:
    # isdigit() accepts Unicode numerals that int() cannot parse (e.g. ²).
    # Only canonical ASCII HH:MM is accepted by the persisted window format.
    return bool(len(s)==5 and s.isascii() and s[2]==':' and
                s[:2].isdigit() and s[3:].isdigit() and
                0<=int(s[:2])<=23 and 0<=int(s[3:])<=59)


def minutes(value: str) -> int:
    return int(value[:2])*60+int(value[3:])


class WindowIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    weekday: int=Field(ge=0,le=6)
    start_time: str
    end_time: str

    @field_validator('start_time','end_time')
    @classmethod
    def parse_clock(cls,value):
        if not valid_time(value):raise ValueError('Use horário HH:MM')
        return value

    @model_validator(mode='after')
    def valid_interval(self):
        if minutes(self.start_time)>=minutes(self.end_time):
            raise ValueError('A disponibilidade deve terminar depois do início')
        return self


def calculate_slots(windows,events,day:date,duration:int,step:int,buffer:int,now=None):
    """Compute zone-aware UTC slot instants; [start,end) overlaps plus buffer."""
    now=now or datetime.now(timezone.utc)
    result=[];seen=set()
    for window in windows:
        begin,end=minutes(window['start_time']),minutes(window['end_time'])
        for pos in range(begin,end-duration+1,step):
            hour,minute=divmod(pos,60)
            local=datetime(day.year,day.month,day.day,hour,minute,tzinfo=LOCAL_ZONE)
            start=local.astimezone(timezone.utc)
            # Avoid inventing a non-existent local hour during clock transitions.
            if start.astimezone(LOCAL_ZONE).replace(tzinfo=None)!=local.replace(tzinfo=None):continue
            finish=start+timedelta(minutes=duration)
            if start<=now or start in seen:continue
            if any(start-timedelta(minutes=buffer)<datetime.fromisoformat(e['end_at']) and
                   finish+timedelta(minutes=buffer)>datetime.fromisoformat(e['start_at']) for e in events):
                continue
            seen.add(start)
            result.append({'start_at':start.isoformat(timespec='seconds'),
                           'end_at':finish.isoformat(timespec='seconds'),
                           'local_start':start.astimezone(LOCAL_ZONE).isoformat(timespec='minutes')})
    return sorted(result,key=lambda row:row['start_at'])[:100]


def register_availability(app: FastAPI,store:Store,require_login):
    @app.get('/api/availability/windows')
    def get_windows(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM availability_windows ORDER BY weekday,start_time,id'))

    @app.post('/api/availability/windows',status_code=201)
    def add_window(data:WindowIn,_=Depends(require_login)):
        with store.transaction() as db:
            count=db.execute('SELECT count(*) FROM availability_windows WHERE weekday=?',(data.weekday,)).fetchone()[0]
            if count>=8:raise HTTPException(422,'Máximo de 8 faixas por dia')
            existing=db.execute('''SELECT 1 FROM availability_windows WHERE weekday=?
                AND start_time<? AND end_time>? LIMIT 1''',(data.weekday,data.end_time,data.start_time)).fetchone()
            if existing:raise HTTPException(409,'Faixa sobreposta à disponibilidade existente')
            ident=new_id()
            db.execute('INSERT INTO availability_windows VALUES (?,?,?,?,?)',
                       (ident,data.weekday,data.start_time,data.end_time,now_utc()))
            record(db,'availability',ident,'create')
        return {'id':ident}

    @app.delete('/api/availability/windows/{ident}')
    def remove_window(ident:str,_=Depends(require_login)):
        with store.transaction() as db:
            result=db.execute('DELETE FROM availability_windows WHERE id=?',(ident,))
            if not result.rowcount:raise HTTPException(404,'Faixa de disponibilidade não encontrada')
            record(db,'availability',ident,'delete')
        return {'deleted':True}

    @app.get('/api/availability/slots')
    def slots(day:str,duration:int=30,step:int=15,buffer:int=0,_=Depends(require_login)):
        try:
            requested=date.fromisoformat(day)
            if requested.isoformat()!=day:raise ValueError('Data inválida')
        except (ValueError,TypeError):
            raise HTTPException(422,'Data no formato AAAA-MM-DD')
        # The response queries [day, day+1). date.max has no successor;
        # reject it instead of leaking an unhandled OverflowError (HTTP 500).
        if requested == date.max:
            raise HTTPException(422,'Data fora do intervalo suportado')
        if not (15<=duration<=180 and 5<=step<=60 and 0<=buffer<=60):
            raise HTTPException(422,'Duração 15–180, passo 5–60 e intervalo 0–60 minutos')
        day_start=datetime.combine(requested,datetime.min.time(),LOCAL_ZONE).astimezone(timezone.utc)
        day_end=datetime.combine(requested+timedelta(days=1),datetime.min.time(),LOCAL_ZONE).astimezone(timezone.utc)
        with store.connection() as db:
            windows=rows(db.execute('SELECT * FROM availability_windows WHERE weekday=?',(requested.weekday(),)))
            # Expand by buffer when finding event blockers; confirmed events only.
            low=(day_start-timedelta(minutes=buffer)).isoformat(timespec='seconds')
            high=(day_end+timedelta(minutes=buffer)).isoformat(timespec='seconds')
            events=rows(db.execute('''SELECT id,start_at,end_at FROM events WHERE status='confirmed'
                AND start_at<? AND end_at>?''',(high,low)))
        return {'day':day,'timezone':'America/Sao_Paulo','duration_minutes':duration,
                'buffer_minutes':buffer,'slots':calculate_slots(windows,events,requested,duration,step,buffer),
                'notice':'Disponibilidade local indicativa; a criação de compromisso confirmado valida novamente eventuais conflitos.'}
