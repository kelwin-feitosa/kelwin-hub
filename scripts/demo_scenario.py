"""Creates only a separate, wholly fictional demo database."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hub.storage import Store,new_id,now_utc
from hub.automation import run_stale


def demo(path:Path):
    if path.exists():
        raise FileExistsError('Banco de demonstração já existe; seus dados foram preservados.')
    store=Store(str(path))
    previous=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat(timespec='seconds')
    project,cid,opp,task=[new_id() for _ in range(4)]
    with store.transaction() as db:
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(project,'Projeto de demonstração','trabalho','active',previous))
        db.execute('INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?)',(cid,'Ana Exemplo','Empresa fictícia','ana@example.test','','business','demo',previous))
        db.execute('INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?)',(opp,cid,'Site institucional fictício','service','waiting',150000,'Verificar resposta',None,previous,previous,previous))
        db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)',(task,'Preparar orçamento fictício',project,opp,'open',2,None,'Conferir escopo',None,previous))
    run_stale(store)
    print('Demonstração criada em',path,'(dados inteiramente fictícios)')


if __name__=='__main__':
    demo(ROOT/'data'/'demo.db')
