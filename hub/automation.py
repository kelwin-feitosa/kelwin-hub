"""Deterministic Atlas A10-02/A02-04: stalled opportunities, no outgoing messages."""
from datetime import datetime, timedelta, timezone
from .storage import new_id, now_utc, rows, record

TEMPLATES = [
    {'code':'stale_opportunities','name':'Oportunidades sem acompanhamento','atlas':'A10-02 / A02-04',
     'description':'Cria alertas locais quando oportunidades ficam sem contato pelo período configurado.',
     'status':'available','engine':'hub','risk':'low'},
    {'code':'meeting_brief','name':'Preparador de reuniões','atlas':'A02-02',
     'description':'Planeja um briefing com documentos autorizados (ainda não implementado).',
     'status':'planned','engine':'optional-n8n','risk':'medium'},
    {'code':'daily_summary','name':'Resumo diário','atlas':'A01-01',
     'description':'Sintetiza tarefas e agenda (ainda não implementado).',
     'status':'planned','engine':'optional-n8n','risk':'low'},
    {'code':'missing_execution','name':'Monitor de falha silenciosa','atlas':'A16-08',
     'description':'Verifica ausência de execução agendada (ainda não implementado).',
     'status':'planned','engine':'hub','risk':'low'},
]


def run_stale(store, *, clock=None):
    moment = clock or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError('clock must be timezone aware')
    moment = moment.astimezone(timezone.utc)
    with store.transaction() as db:
        conf = db.execute("SELECT * FROM automation_configs WHERE code='stale_opportunities'").fetchone()
        if not conf or not conf['enabled']:
            return {'executed':False,'reason':'disabled','scanned':0,'created':0}
        limit = (moment - timedelta(days=conf['threshold_days'])).isoformat(timespec='seconds')
        relevant = rows(db.execute('''SELECT id,title,last_contact_at,created_at
            FROM opportunities WHERE status IN ('new','active','waiting')
              AND COALESCE(last_contact_at,created_at) <= ?''', (limit,)))
        created = 0
        for op in relevant:
            # Dismissal silences this episode until a subsequent recorded interaction.
            if db.execute("SELECT 1 FROM alerts WHERE code='stale_opportunities' AND entity_id=? AND status='dismissed' AND closed_at>=? LIMIT 1",
                          (op['id'], op['last_contact_at'] or op['created_at'])).fetchone():
                continue
            ident = new_id()
            before = db.total_changes
            db.execute('''INSERT OR IGNORE INTO alerts(id,code,entity_id,title,status,created_at)
                VALUES (?,?,?,?,'open',?)''',
                (ident,'stale_opportunities',op['id'],f"Revisar: {op['title']}",moment.isoformat(timespec='seconds')))
            created += db.total_changes - before
        db.execute("UPDATE automation_configs SET last_run_at=? WHERE code='stale_opportunities'",
                   (moment.isoformat(timespec='seconds'),))
        db.execute('INSERT INTO automation_runs VALUES (?,?,?,?,?,?,?)',
                   (new_id(),'stale_opportunities','ok',len(relevant),created,moment.isoformat(timespec='seconds'),''))
        record(db,'automation','stale_opportunities','run')
        return {'executed':True,'scanned':len(relevant),'created':created,'threshold_days':conf['threshold_days']}


def safe_run_stale(store, *, clock=None):
    try:
        return run_stale(store, clock=clock)
    except Exception as exc:
        # Persist only the exception class, never sensitive exception text.
        with store.transaction() as db:
            db.execute('INSERT INTO automation_runs VALUES (?,?,?,?,?,?,?)',
                       (new_id(),'stale_opportunities','failed',0,0,now_utc(),type(exc).__name__))
        raise
