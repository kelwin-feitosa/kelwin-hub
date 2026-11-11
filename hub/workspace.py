"""Read-only contextual work projection; existing entities remain the source of truth.

No new tables, synchronization loops or duplicated task/opportunity records.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .storage import rows

LOCAL_TZ = ZoneInfo('America/Sao_Paulo')


def _group(due: str | None, priority: int, *, today) -> str:
    if priority == 3:
        return 'now'
    if not due:
        return 'next'
    day = datetime.fromisoformat(due.replace('Z', '+00:00'))
    if day.tzinfo is None:
        day = day.replace(tzinfo=timezone.utc)
    local_day = day.astimezone(LOCAL_TZ).date()
    if local_day <= today:
        return 'now'
    if local_day <= today + timedelta(days=7):
        return 'next'
    return 'later'


def load_workspace(store, *, moment: datetime | None = None):
    """Join local work once, suppressing opportunity prompts with an active linked task.

    The client receives source IDs, not synthetic copies; all mutations still use
    the existing authenticated resource endpoints.
    """
    current = (moment or datetime.now(LOCAL_TZ)).astimezone(LOCAL_TZ)
    day = current.date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end = (datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ) + timedelta(days=1)).astimezone(timezone.utc)
    with store.connection() as db:
        tasks = rows(db.execute('''
            SELECT t.id,t.title,t.status,t.priority,t.due_at,t.next_action,
                   t.project_id,p.name AS project_name,
                   t.opportunity_id,o.title AS opportunity_title,
                   c.name AS contact_name
              FROM tasks t
              LEFT JOIN projects p ON p.id=t.project_id
              LEFT JOIN opportunities o ON o.id=t.opportunity_id
              LEFT JOIN contacts c ON c.id=o.contact_id
             WHERE t.status IN ('open','blocked')
        '''))
        opportunities = rows(db.execute('''
            SELECT o.id,o.title,o.status,o.next_action,o.followup_at AS due_at,
                   o.contact_id,c.name AS contact_name
              FROM opportunities o JOIN contacts c ON c.id=o.contact_id
             WHERE o.status IN ('new','active','waiting')
               AND NOT EXISTS (
                 SELECT 1 FROM tasks t
                  WHERE t.opportunity_id=o.id AND t.status IN ('open','blocked')
               )
        '''))
        events = rows(db.execute('''
            SELECT id,title,start_at,end_at,status,source FROM events
             WHERE start_at < ? AND end_at > ? AND status!='cancelled'
             ORDER BY start_at
        ''', (end.isoformat(timespec='seconds'), start.isoformat(timespec='seconds'))))
        alerts = rows(db.execute('''
            SELECT id,title,created_at FROM alerts WHERE status='open'
             ORDER BY created_at DESC LIMIT 10
        '''))
    groups = {'now': [], 'next': [], 'later': [], 'blocked': []}
    for task in tasks:
        kind = 'task'
        group = 'blocked' if task['status'] == 'blocked' else _group(task['due_at'], task['priority'], today=day)
        groups[group].append({**task, 'kind': kind, 'group': group})
    for opportunity in opportunities:
        group = _group(opportunity['due_at'], 1, today=day)
        groups[group].append({**opportunity, 'kind': 'opportunity', 'group': group, 'priority': 1,
                              'project_id': None, 'project_name': None,
                              'opportunity_id': opportunity['id'], 'opportunity_title': opportunity['title']})
    for items in groups.values():
        items.sort(key=lambda x: (
            x['due_at'] is None,
            x['due_at'] or '',
            -x['priority'],
            x['title'].casefold(),
            x['id'],
        ))
    return {
        'local_date': day.isoformat(),
        'groups': groups,
        'events': events,
        'alerts': alerts,
        'total_actions': sum(len(items) for items in groups.values()),
    }
