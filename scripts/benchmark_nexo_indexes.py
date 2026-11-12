"""Standalone synthetic SQLite benchmark; never access an existing Hub DB."""
import sqlite3, tempfile, time, statistics, uuid, random
from pathlib import Path

SQL = '''SELECT id,title,status,priority,due_at,created_at FROM tasks WHERE project_id=? ORDER BY CASE status WHEN 'blocked' THEN 1 WHEN 'open' THEN 0 ELSE 2 END,CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,due_at ASC,priority DESC,created_at DESC'''

with tempfile.TemporaryDirectory(prefix='nexo-bench-') as dir:
 db=sqlite3.connect(str(Path(dir)/'synthetic.db'),cached_statements=0)
 db.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY,title TEXT,status TEXT,priority INTEGER,due_at TEXT,created_at TEXT,project_id TEXT,opportunity_id TEXT)')
 rng=random.Random(42)
 for size in [500,5000,20000]:
  db.execute('DELETE FROM tasks')
  batch=[(str(i),f'Tarefa {i}',rng.choice(['open','done','blocked']),rng.randrange(4),None if i%3 else '2027-01-15T10:00:00Z','2026-11-12T14:00:00Z',f'p{i%100}',f'o{i%250}') for i in range(size)]
  db.executemany('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',batch)
  db.commit()
  for has_index in (False,True):
   if has_index: db.execute('CREATE INDEX task_project_context_idx ON tasks(project_id,status,due_at,created_at)')
   else: db.execute('DROP INDEX IF EXISTS task_project_context_idx')
   db.execute(SQL,('p13',)).fetchall()
   samples=[]
   for i in range(150):
    t0=time.perf_counter_ns(); db.execute(SQL,(f'p{i%100}',)).fetchall();samples.append((time.perf_counter_ns()-t0)/1e6)
   samples.sort();print(size,'index' if has_index else 'scan','median_ms',round(statistics.median(samples),4),'p95_ms',round(samples[int(.95*len(samples))],4),'plan',[x[3] for x in db.execute('EXPLAIN QUERY PLAN '+SQL,('p13',))])