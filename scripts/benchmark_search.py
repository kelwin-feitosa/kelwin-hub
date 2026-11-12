"""Representative local benchmark of search, no user data or paid dependencies.

Run from repository root: python scripts/benchmark_search.py.
Baseline comparison is the original logic preserved for this one-off study.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub.search import search


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
        queries = ('musica', 'musicxml', 'projeto', 'revisao', 'ana', 'nao existe', 'Projeto Musica 42')
        for q in queries:
            search(store, q)  # warmup
        times=[]
        for _ in range(9):
            for q in queries:
                start = time.perf_counter()
                search(store, q)
                times.append((time.perf_counter() - start) * 1000)
        print({'rows': 7000, 'queries': queries, 'results': {
            'p50_ms': round(statistics.median(times), 2),
            'p95_ms': round(quantile(times, .95), 2),
            'samples': len(times)}})

if __name__=='__main__':main()
