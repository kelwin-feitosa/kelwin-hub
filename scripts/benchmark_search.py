"""Representative local benchmark of search, no user data or paid dependencies.

Run from repository root: python scripts/benchmark_search.py.
Baseline comparison is the original logic preserved for this one-off study.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import statistics
import unicodedata
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub.search import search, KINDS


from contextlib import contextmanager


class SearchStore:
    """SQLite-only fixture; never opens the user's database or runs migrations."""
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connection(self):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            yield db


def legacy_folded(value):
    raw = unicodedata.normalize('NFKD', str(value or ''))
    return ''.join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def legacy_search(store, query, *, per_kind=8, total=40):
    """Pre-18.2 implementation retained as a benchmark equivalence oracle."""
    query = ' '.join(query.split())
    if not (2 <= len(query) <= 100):
        raise ValueError('Use entre 2 e 100 caracteres para pesquisar')
    normalized_query = legacy_folded(query)
    words = normalized_query.split()
    found = []
    truncated_by_kind = False
    with store.connection() as db:
        for kind_order, (kind, spec) in enumerate(KINDS.items()):
            candidates = []
            for row in db.execute(spec['sql']):
                item = dict(row)
                title = legacy_folded(item['title'])
                title_matches = all(term in title for term in words)
                if not title_matches:
                    context = legacy_folded(' '.join(str(item.get(k) or '')
                                               for k in ('detail', 'terms')))
                    if not all(term in title or term in context for term in words):
                        continue
                rank = (0 if title == normalized_query else
                        1 if title.startswith(normalized_query) else
                        2 if title_matches else 3)
                candidates.append((rank, title, {
                    'id': item['id'], 'kind': kind,
                    'label': spec['label'], 'title': item['title'],
                    'detail': item.get('detail') or '', 'status': item['status']}))
            candidates.sort(key=lambda row: (row[0], row[1]))
            truncated_by_kind |= len(candidates) > per_kind
            found.extend((rank, kind_order, item) for rank, _, item in candidates[:per_kind])
    found.sort(key=lambda row: (row[0], row[1], legacy_folded(row[2]['title'])))
    return {'query': query, 'results': [item for _, _, item in found[:total]],
            'limited': truncated_by_kind or len(found) > total}


def seed(path):
    with sqlite3.connect(path) as db:
        db.executescript('''
        CREATE TABLE projects (id TEXT, name TEXT, area TEXT, status TEXT);
        CREATE TABLE tasks (id TEXT, title TEXT, project_id TEXT, opportunity_id TEXT, status TEXT, next_action TEXT);
        CREATE TABLE contacts (id TEXT, name TEXT, company TEXT, category TEXT, email TEXT, phone TEXT);
        CREATE TABLE opportunities (id TEXT, title TEXT, contact_id TEXT, status TEXT, next_action TEXT);
        CREATE TABLE notes (id TEXT, title TEXT, body TEXT, project_id TEXT, contact_id TEXT, opportunity_id TEXT);
        CREATE TABLE events (id TEXT, title TEXT, start_at TEXT, status TEXT);
        ''')
        db.executemany('INSERT INTO projects VALUES (?,?,?,?)', [(str(i), f'Projeto Música {i}', 'estudo','active') for i in range(800)])
        db.executemany('INSERT INTO contacts VALUES (?,?,?,?,?,?)', [(str(i), f'Ana Contato {i}', 'Empresa', 'business', f'ana{i}@example.test','') for i in range(300)])
        db.executemany('INSERT INTO opportunities VALUES (?,?,?,?,?)', [(str(i), f'Projeto MusicXML {i}', str(i % 300), 'active', 'Enviar proposta') for i in range(600)])
        db.executemany('INSERT INTO tasks VALUES (?,?,?,?,?,?)', [(str(i),f'Revisão de música {i}', str(i % 800), str(i%600),'open','Acompanhar progresso') for i in range(4500)])
        db.executemany('INSERT INTO notes VALUES (?,?,?,?,?,?)', [(str(i),f'Nota sobre projeto {i}', 'Flauta e processamento MusicXML. ' * 4, str(i%800), None,None) for i in range(600)])
        db.executemany('INSERT INTO events VALUES (?,?,?,?)', [(str(i),f'Reunião de projeto {i}','2026-11-12T12:00:00+00:00','confirmed') for i in range(200)])


def quantile(xs, p):
    return sorted(xs)[round((len(xs)-1)*p)]


def main():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'synthetic.db')
        seed(path)
        store = SearchStore(path)
        queries = ('musica', 'musicxml', 'projeto', 'revisao', 'ana',
                   'nao existe', 'Projeto Musica 42', '100%', 'na', 'ação')
        for q in queries:
            expected=legacy_search(store,q)
            assert search(store,q)==expected, ('Search semantics changed',q)
        samples={'legacy_reference': [], 'bounded_search': []}
        for _ in range(9):
            for q in queries:
                for name,fn in (('legacy_reference',legacy_search),
                                ('bounded_search',search)):
                    start=time.perf_counter()
                    result=fn(store,q)
                    samples[name].append((time.perf_counter()-start)*1000)
                    assert result==legacy_search(store,q), ('Mismatch',q)
        print({'environment':'same temporary SQLite; 7000 fictional rows',
               'queries':queries,'samples_per_approach':len(samples['bounded_search']),
               'times_ms':{
                   name:{'p50':round(statistics.median(values),2),
                         'p95':round(quantile(values,.95),2)}
                   for name,values in samples.items()},
               'limitations':'Function-level comparison; does not measure HTTP, memory RSS, or browser paint.'})


if __name__=='__main__':
    main()
