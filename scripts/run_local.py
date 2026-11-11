"""Safe local launcher; uses only the specific project .env file."""
from pathlib import Path
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))


def load_env():
    path=ROOT/'.env'
    if not path.exists():
        raise SystemExit('Arquivo .env ausente. Execute: python3 scripts/init_env.py')
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        if key in {'HUB_PASSWORD_HASH','HUB_SESSION_SECRET','HUB_INTERNAL_TOKEN','HUB_DB_PATH','HUB_SCHEDULER','HUB_COOKIE_SECURE','N8N_ENCRYPTION_KEY'}:
            os.environ.setdefault(key,value)


if __name__=='__main__':
    load_env()
    import uvicorn
    uvicorn.run('hub.server:app',host='127.0.0.1',port=8000,proxy_headers=False)
