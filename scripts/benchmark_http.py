"""Synthetic HTTP response benchmark for the local Hub, no external network.

Measures complete FastAPI TestClient roundtrips, not browser paint. All test
entities and credentials are fictional and live in a temporary SQLite file.
"""
import argparse
from pathlib import Path
from statistics import median
import tempfile
from time import perf_counter
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password


def percentile95(samples):
    seq=sorted(samples)
    return seq[max(0,(95*len(seq)+99)//100-1)]


def benchmark(records=1000,iterations=30):
    if not 0<=records<=5000 or not 2<=iterations<=200:
        raise ValueError('Use 0–5000 registros e 2–200 repetições')
    password='Bench-synthetic-password-2026!'
    with tempfile.TemporaryDirectory(prefix='kh16-benchmark-') as dirname:
        app=create_app(str(Path(dirname)/'synthetic.db'),
                       password_hash=hash_password(password),
                       session_secret='S'*48,scheduler=False)
        store=app.state.store
        with store.transaction() as db:
            db.executemany('''INSERT INTO tasks
                (id,title,project_id,opportunity_id,status,priority,due_at,next_action,
                 completed_at,created_at,estimated_minutes)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                [(f'task-{i}',f'Tarefa sintética {i}',None,None,
                  'open' if i%7 else 'done',i%4,
                  None if i%3 else '2027-01-01T10:00:00+00:00',
                  '',None,'2026-11-12T10:00:00+00:00',30 if i%2 else None)
                 for i in range(records)])
        routes={'tasks_page':'/api/tasks/page?limit=30&offset=0',
                'tasks_all_legacy':'/api/tasks',
                'focus_30min':'/api/focus?minutes=30',
                'workspace':'/api/workspace'}
        output={}
        with TestClient(app) as client:
            assert client.post('/api/login',json={'password':password}).status_code==200
            for name,endpoint in routes.items():
                for _ in range(3):
                    assert client.get(endpoint).status_code==200
                durations=[]
                payload_bytes=[]
                for _ in range(iterations):
                    begin=perf_counter()
                    response=client.get(endpoint)
                    durations.append((perf_counter()-begin)*1000)
                    assert response.status_code==200,response.text
                    payload_bytes.append(len(response.content))
                output[name]={'p50_ms':round(median(durations),3),
                              'p95_ms':round(percentile95(durations),3),
                              'response_bytes':round(median(payload_bytes))}
    return {'environment':'synthetic FastAPI TestClient with SQLite tempfile',
            'tasks':records,'iterations_per_route':iterations,'routes':output,
            'limitations':'No real browser paint, real device, concurrent users or post-merge gain claim.'}


def main():
    parser=argparse.ArgumentParser(description='Métrica HTTP sintética sem acessar banco pessoal')
    parser.add_argument('--tasks',type=int,default=1000)
    parser.add_argument('--iterations',type=int,default=30)
    args=parser.parse_args()
    report=benchmark(args.tasks,args.iterations)
    import json
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
