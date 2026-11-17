"""Bounded, read-only contextual work projection over existing entities.

Actions are streamed from SQLite and retained in bounded sorted groups: the
personal dashboard is not a second source of truth or a synchronization loop.
"""
from bisect import insort
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .storage import rows

LOCAL_TZ = ZoneInfo('America/Sao_Paulo')
GROUPS = ('now', 'next', 'later', 'blocked')


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


def _ordering(item: dict):
    """Preserve the original stable, human-facing order for every group."""
    return (item['due_at'] is None, item['due_at'] or '',
            -item['priority'], item['title'].casefold(), item['id'], item['kind'])


def _project_actions(db, today, capacities: dict[str, int]):
    """One pass over the underlying cursors; O(actions × log(page-size)) memory bounded.

    Sorting by a user-visible Unicode title and local due date is intentionally
    left in Python to preserve the existing semantics of the Mesa.
    """
    counts = {group: 0 for group in GROUPS}
    kept = {group: [] for group in GROUPS}

    def consider(item, group):
        counts[group] += 1
        limit = capacities.get(group, 0)
        if limit <= 0:
            return
        selected = kept[group]
        key = _ordering(item)
        if len(selected) < limit:
            insort(selected, (key, item))
        elif key < selected[-1][0]:
            insort(selected, (key, item))
            selected.pop()

    task_sql = """
        SELECT t.id,t.title,t.status,t.priority,t.due_at,t.next_action,
               t.project_id,p.name AS project_name,
               t.opportunity_id,o.title AS opportunity_title,
               c.name AS contact_name
          FROM tasks t
          LEFT JOIN projects p ON p.id=t.project_id
          LEFT JOIN opportunities o ON o.id=t.opportunity_id
          LEFT JOIN contacts c ON c.id=o.contact_id
         WHERE t.status IN ('open','blocked')
    """
    for row in db.execute(task_sql):
        task = dict(row)
        group = 'blocked' if task['status'] == 'blocked' else _group(
            task['due_at'], task['priority'], today=today)
        consider({**task, 'kind': 'task', 'group': group}, group)

    opportunities_sql = """
        SELECT o.id,o.title,o.status,o.next_action,o.followup_at AS due_at,
               o.contact_id,c.name AS contact_name
          FROM opportunities o JOIN contacts c ON c.id=o.contact_id
         WHERE o.status IN ('new','active','waiting')
           AND NOT EXISTS (
             SELECT 1 FROM tasks t
              WHERE t.opportunity_id=o.id AND t.status IN ('open','blocked')
           )
    """
    for row in db.execute(opportunities_sql):
        opportunity = dict(row)
        group = _group(opportunity['due_at'], 1, today=today)
        consider({**opportunity, 'kind': 'opportunity', 'group': group, 'priority': 1,
                  'project_id': None, 'project_name': None,
                  'opportunity_id': opportunity['id'],
                  'opportunity_title': opportunity['title']}, group)
    return ({g: [item for _, item in kept[g]] for g in GROUPS}, counts)


def _local_day_bounds(moment):
    current = (moment or datetime.now(LOCAL_TZ)).astimezone(LOCAL_TZ)
    day = current.date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end = (datetime.combine(day, datetime.min.time(), tzinfo=LOCAL_TZ) + timedelta(days=1)).astimezone(timezone.utc)
    return day, start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds')


def load_workspace(store, *, moment: datetime | None = None,
                   per_group: int = 12, events_limit: int = 12):
    """Small initial Mesa payload, exact counts and explicit continuation."""
    if not (1 <= per_group <= 50 and 0 <= events_limit <= 50):
        raise ValueError('Limites da Mesa inválidos')
    day, start, end = _local_day_bounds(moment)
    with store.connection() as db:
        groups, counts = _project_actions(db, day, dict.fromkeys(GROUPS, per_group))
        event_where = "start_at < ? AND end_at > ? AND status!='cancelled'"
        event_total = db.execute(
            'SELECT COUNT(*) FROM events WHERE ' + event_where, (end, start)
        ).fetchone()[0]
        events = rows(db.execute(
            'SELECT id,title,start_at,end_at,status,source FROM events WHERE ' +
            event_where + ' ORDER BY start_at, id LIMIT ?',
            (end, start, events_limit)))
        alerts = rows(db.execute(
            "SELECT id,title,created_at FROM alerts WHERE status='open' "
            "ORDER BY created_at DESC LIMIT 10"))
    return {
        'local_date': day.isoformat(),
        'groups': groups,
        'group_counts': counts,
        'events': events,
        'events_total': event_total,
        'alerts': alerts,
        'total_actions': sum(counts.values()),
    }


def load_workspace_group(store, group: str, *, offset: int = 0, limit: int = 30,
                         moment: datetime | None = None):
    """Continue a group without materializing all actions into the response."""
    if group not in GROUPS or not (0 <= offset <= 5000 and 1 <= limit <= 100):
        raise ValueError('Grupo ou paginação inválidos')
    day, _, _ = _local_day_bounds(moment)
    with store.connection() as db:
        groups, counts = _project_actions(db, day, {group: offset + limit})
    page = groups[group][offset:offset + limit]
    return {
        'group': group,
        'local_date': day.isoformat(),
        'items': page,
        'total': counts[group],
        'offset': offset,
        'limit': limit,
        'has_more': offset + len(page) < counts[group],
    }
