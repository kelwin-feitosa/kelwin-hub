"""Read-only opportunity projection; no inferred relations or copied data."""
from .storage import rows


def load_opportunity_context(store, ident: str) -> dict | None:
    with store.connection() as db:
        item = db.execute("""
            SELECT o.*, c.name AS contact_name, c.company AS contact_company
              FROM opportunities o JOIN contacts c ON c.id=o.contact_id
             WHERE o.id=?
        """, (ident,)).fetchone()
        if item is None:
            return None
        tasks=rows(db.execute("""
            SELECT id,title,status,priority,due_at,project_id,created_at
              FROM tasks WHERE opportunity_id=?
             ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'blocked' THEN 1 ELSE 2 END,
                      CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                      due_at,priority DESC,created_at DESC
             LIMIT 60
        """, (ident,)))
        notes=rows(db.execute("""
            SELECT id,title,substr(body,1,220) AS body,updated_at
              FROM notes WHERE opportunity_id=?
             ORDER BY updated_at DESC,id DESC LIMIT 8
        """, (ident,)))
        activity=rows(db.execute("""
            SELECT a.kind,a.action,a.at FROM audit a
             WHERE (a.kind='opportunity' AND a.entity_id=?)
                OR (a.kind='task' AND EXISTS(
                    SELECT 1 FROM tasks t WHERE t.id=a.entity_id AND t.opportunity_id=?))
                OR (a.kind='note' AND EXISTS(
                    SELECT 1 FROM notes n WHERE n.id=a.entity_id AND n.opportunity_id=?))
             ORDER BY a.at DESC,a.id DESC LIMIT 12
        """, (ident,ident,ident)))
        open_tasks=[t for t in tasks if t['status']=='open']
        return {
            'opportunity':dict(item), 'tasks':tasks,
            'notes':notes, 'recent_activity':activity,
            'next_task':open_tasks[0] if open_tasks else None,
            'counts':{'open':len(open_tasks),
                      'blocked':sum(t['status']=='blocked' for t in tasks),
                      'done':sum(t['status']=='done' for t in tasks)},
            'limits':{'tasks':60,'notes':8,'activity':12}
        }
