"""Generate a local .env without storing the plaintext login password."""
import getpass
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hub.security import hash_password


def main():
    target = ROOT/'.env'
    if target.exists():
        raise SystemExit('.env já existe; preservado. Para alterar credenciais, faça backup antes.')
    password = getpass.getpass('Crie uma senha local (mínimo 12 caracteres): ')
    confirm = getpass.getpass('Confirme a senha: ')
    if password != confirm:
        raise SystemExit('Senhas diferentes. Arquivo não criado.')
    hashed = hash_password(password)
    contents = '\n'.join([
        '# Gerado localmente. NÃO publicar nem compartilhar.',
        f'HUB_PASSWORD_HASH={hashed}',
        f'HUB_SESSION_SECRET={secrets.token_urlsafe(48)}',
        f'HUB_INTERNAL_TOKEN={secrets.token_urlsafe(40)}',
        f'N8N_ENCRYPTION_KEY={secrets.token_urlsafe(32)}',
        'HUB_DB_PATH=./data/hub.db',
        'HUB_SCHEDULER=1',
        'HUB_COOKIE_SECURE=0',
        '',
    ])
    # chmod after write is too late: a permissive umask could expose the
    # credentials before chmod. O_EXCL also prevents an overwrite race.
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit('.env já existe; preservado. Para alterar credenciais, faça backup antes.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(contents)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    print('Configuração privada criada em .env')

if __name__=='__main__':
    main()
