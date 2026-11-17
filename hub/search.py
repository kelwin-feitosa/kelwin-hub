"""Local-only universal search of existing entities, without duplicated indexes.

Small single-user SQLite dataset: accent-insensitive Unicode matching in Python
avoids creating a permanently synchronized search database. Read-only.
"""
import unicodedata
from heapq import nsmallest

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
    raw = str(value or '')
    # ASCII text has no combining accents to remove. Avoid costly NFKD and
    # per-character generator work in the common case without changing results.
    if raw.isascii():
        return raw.casefold()
    raw = unicodedata.normalize('NFKD', raw)
    return ''.join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def search(store, query: str, *, per_kind: int = 8, total: int = 40) -> dict:
    query = ' '.join(query.split())
    if not (2 <= len(query) <= 100):
        raise ValueError('Use entre 2 e 100 caracteres para pesquisar')
    if not (1 <= per_kind <= 100 and 1 <= total <= 100):
        raise ValueError('Limites da pesquisa inválidos')
    normalized_query = folded(query)
    words = normalized_query.split()
    found = []
    truncated_by_kind = False
    with store.connection() as db:
        for kind_order, (kind, spec) in enumerate(KINDS.items()):
            match_count = 0

            def matching_rows():
                nonlocal match_count
                # Iterate the cursor without materializing an entire collection
                # or building result dictionaries for non-matching records.
                for ordinal, row in enumerate(db.execute(spec['sql'])):
                    title = folded(row['title'])
                    title_matches = all(term in title for term in words)
                    if not title_matches:
                        related = ' '.join(str(row[key] or '')
                                           for key in ('detail', 'terms') if key in row.keys())
                        context = folded(related)
                        if not all(term in title or term in context for term in words):
                            continue
                    rank = (0 if title == normalized_query else
                            1 if title.startswith(normalized_query) else
                            2 if title_matches else 3)
                    match_count += 1
                    yield (rank, title, ordinal, {
                        'id': row['id'], 'kind': kind, 'label': spec['label'],
                        'title': row['title'], 'detail': row['detail'] or '',
                        'status': row['status'],
                    })

            # Keep exactly the original top-per-kind order and stable ties.
            # The heap holds at most per_kind matches, even for 20k notes.
            best = nsmallest(per_kind, matching_rows(), key=lambda x: x[:3])
            truncated_by_kind |= match_count > per_kind
            found.extend((rank, kind_order, title, item)
                         for rank, title, _, item in best)
    found.sort(key=lambda row: (row[0], row[1], row[2]))
    return {
        'query': query,
        'results': [item for _, _, _, item in found[:total]],
        'limited': truncated_by_kind or len(found) > total,
    }
