"""Read-only, explainable groups for contact follow-up (not a new CRM state)."""
from datetime import datetime, timedelta, timezone

from .storage import rows

ACTIVE = frozenset({'new', 'active', 'waiting'})


def load_board(store, *, now=None):
    now = now or datetime.now(timezone.utc)
    soon = now + timedelta(days=7)
    grouped = {name: [] for name in ('overdue','upcoming','later','awaiting','undated','closed')}
    with store.connection() as db:
        opportunities = rows(db.execute('''
            SELECT o.*, c.name AS contact_name, c.email AS contact_email
            FROM opportunities o JOIN contacts c ON c.id=o.contact_id
            ORDER BY o.created_at DESC
        '''))
    for item in opportunities:
        due = datetime.fromisoformat(item['followup_at'].replace('Z','+00:00')) if item['followup_at'] else None
        if due and due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if item['status'] not in ACTIVE:
            group='closed'
        elif due and due < now:
            group='overdue'
        elif due and due <= soon:
            group='upcoming'
        elif due:
            group='later'
        elif item['status']=='waiting':
            group='awaiting'
        else:
            group='undated'
        grouped[group].append(item)
    for name in ('overdue','upcoming','later'):
        grouped[name].sort(key=lambda x:(x['followup_at'] or '',x['title'].casefold()))
    return {'groups':grouped,'counts':{k:len(v) for k,v in grouped.items()},'generated_at':now.isoformat()}
