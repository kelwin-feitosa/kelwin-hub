"""Generate a local .env without storing the plaintext login password."""
import getpass
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
    target.write_text('\n'.join([
        '# Gerado localmente. NÃO publicar nem compartilhar.',
        f'HUB_PASSWORD_HASH={hashed}',
        f'HUB_SESSION_SECRET={secrets.token_urlsafe(48)}',
        f'HUB_INTERNAL_TOKEN={secrets.token_urlsafe(40)}',
        f'N8N_ENCRYPTION_KEY={secrets.token_urlsafe(32)}',
        'HUB_DB_PATH=./data/hub.db',
        'HUB_SCHEDULER=1',
        'HUB_COOKIE_SECURE=0',
        '',
    ]))
    target.chmod(0o600)
    print('Configuração privada criada em .env')

if __name__=='__main__':
    main()
