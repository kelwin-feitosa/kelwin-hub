"""Read-only project detail from canonical tasks/audit, no duplicate storage."""
from .storage import rows


def load_project_context(store, ident: str) -> dict | None:
    with store.connection() as db:
        project = db.execute('SELECT * FROM projects WHERE id=?', (ident,)).fetchone()
        if project is None:
            return None
        tasks = rows(db.execute('''
            SELECT t.id, t.title, t.status, t.priority, t.due_at,
                   t.next_action, t.opportunity_id, o.title AS opportunity_title
            FROM tasks t LEFT JOIN opportunities o ON o.id=t.opportunity_id
            WHERE t.project_id=?
            ORDER BY CASE t.status WHEN 'blocked' THEN 1 WHEN 'open' THEN 0 ELSE 2 END,
                     CASE WHEN t.due_at IS NULL THEN 1 ELSE 0 END,
                     t.due_at ASC, t.priority DESC, t.created_at DESC
        ''', (ident,)))
        open_tasks = [t for t in tasks if t['status']=='open']
        blocked = [t for t in tasks if t['status']=='blocked']
        activity = rows(db.execute('''
            SELECT a.action,a.at,a.kind FROM audit a
            WHERE (a.kind='project' AND a.entity_id=?)
               OR (a.kind='task' AND EXISTS (
                 SELECT 1 FROM tasks t WHERE t.id=a.entity_id AND t.project_id=?))
            ORDER BY a.at DESC LIMIT 10
        ''', (ident,ident)))
        return {
            'project': dict(project), 'tasks': tasks,
            'counts': {'open':len(open_tasks),'blocked':len(blocked),
                       'done':sum(t['status']=='done' for t in tasks)},
            'next_task': open_tasks[0] if open_tasks else None,
            'recent_activity': activity,
        }
