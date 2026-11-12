"""Local-only universal search of existing entities, without duplicated indexes.

Small single-user SQLite dataset: accent-insensitive Unicode matching in Python
avoids creating a permanently synchronized search database. Read-only.
"""
import unicodedata

from .storage import rows

KINDS = {
    'projects': {
        'label': 'Projetos',
        'sql': 'SELECT id, name AS title, area AS detail, status FROM projects',
    },
    'tasks': {
        'label': 'Tarefas',
        'sql': '''SELECT t.id, t.title,
                  COALESCE(p.name, o.title, '') AS detail,
                  t.status, COALESCE(p.name,'') || ' ' || COALESCE(o.title,'') || ' ' || COALESCE(t.next_action,'') AS terms
                  FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
                  LEFT JOIN opportunities o ON o.id=t.opportunity_id''',
    },
    'contacts': {
        'label': 'Contatos',
        'sql': '''SELECT id, name AS title, company AS detail, category AS status,
                  COALESCE(email,'') || ' ' || phone AS terms FROM contacts''',
    },
    'opportunities': {
        'label': 'Oportunidades',
        'sql': '''SELECT o.id, o.title, c.name AS detail, o.status,
                  c.name || ' ' || c.company || ' ' || COALESCE(c.email, '') || ' ' || o.next_action AS terms
                  FROM opportunities o JOIN contacts c ON c.id=o.contact_id''',
    },
    'notes': {
        'label': 'Notas',
        'sql': '''SELECT n.id, n.title, substr(n.body,1,160) AS detail, 'note' AS status,
                  n.body || ' ' || COALESCE(p.name,'') || ' ' || COALESCE(c.name,'') || ' ' || COALESCE(o.title,'') AS terms
                  FROM notes n LEFT JOIN projects p ON p.id=n.project_id
                  LEFT JOIN contacts c ON c.id=n.contact_id
                  LEFT JOIN opportunities o ON o.id=n.opportunity_id''',
    },
    'events': {
        'label': 'Agenda',
        'sql': 'SELECT id, title, start_at AS detail, status FROM events',
    },
}


def folded(value: object) -> str:
    """Case- and accent-insensitive search, including composed Unicode forms."""
    raw = unicodedata.normalize('NFKD', str(value or ''))
    return ''.join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def search(store, query: str, *, per_kind: int = 8, total: int = 40) -> dict:
    query = ' '.join(query.split())
    if not (2 <= len(query) <= 100):
        raise ValueError('Use entre 2 e 100 caracteres para pesquisar')
    words = folded(query).split()
    found = []
    with store.connection() as db:
        for kind, spec in KINDS.items():
            candidates = []
            for item in rows(db.execute(spec['sql'])):
                title = folded(item['title'])
                context = folded(' '.join(str(item.get(k) or '') for k in ('detail','terms')))
                if not all(term in title or term in context for term in words):
                    continue
                # Exact title > starts-with > title token > context-only.
                rank = 0 if title == folded(query) else 1 if title.startswith(folded(query)) else 2 if all(w in title for w in words) else 3
                candidates.append((rank, title, {'id': item['id'], 'kind': kind,
                   'label': spec['label'], 'title': item['title'],
                   'detail': item.get('detail') or '', 'status': item['status']}))
            candidates.sort(key=lambda row: (row[0], row[1]))
            found.extend((rank, order, item) for rank, _, item in candidates[:per_kind] for order in [list(KINDS).index(kind)])
    found.sort(key=lambda row: (row[0], row[1], folded(row[2]['title'])))
    return {'query': query, 'results': [item for _, _, item in found[:total]], 'limited': len(found) > total}
