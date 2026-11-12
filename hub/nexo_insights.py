"""Explainable, read-only local suggestions. No automatic actions or state."""
from .storage import rows


def load_suggestions(store) -> list[dict]:
    """Only return observations directly supported by canonical rows."""
    with store.connection() as db:
        meetings = rows(db.execute('''
            SELECT mt.id AS transcript_id, e.title AS event_title,
                   COUNT(s.id) AS pending_items
              FROM meeting_suggestions s
              JOIN meeting_analyses a ON a.id=s.analysis_id
              JOIN meeting_transcripts mt ON mt.id=a.transcript_id
              JOIN events e ON e.id=mt.event_id
             WHERE s.status='proposed'
             GROUP BY mt.id,e.title
             ORDER BY MAX(s.created_at) DESC,mt.id DESC LIMIT 2
        '''))
        projects = rows(db.execute('''
            SELECT p.id,p.name FROM projects p
             WHERE p.status='active'
               AND NOT EXISTS(
                   SELECT 1 FROM tasks t WHERE t.project_id=p.id
                    AND t.status IN ('open','blocked')
               )
             ORDER BY p.created_at DESC,p.id DESC LIMIT 3
        '''))
    suggestions = []
    for item in meetings:
        count = item['pending_items']
        suggestions.append({
            'kind':'meeting_review', 'id':item['transcript_id'],
            'title':item['event_title'],
            'reason':f'{count} item(ns) aguardando revisão humana.',
            'evidence':{'pending_items':count},
        })
    for item in projects:
        suggestions.append({
            'kind':'project_next_step', 'id':item['id'],
            'title':item['name'],
            'reason':'Projeto ativo sem tarefa aberta ou bloqueada. Verifique se existe uma próxima ação.',
            'evidence':{'status':'active','open_or_blocked_tasks':0},
        })
    return suggestions[:3]