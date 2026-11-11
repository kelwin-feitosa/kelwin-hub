"""Encrypted consistent backup and deliberately non-destructive restore.

Install `pip install '.[backup]'`; snapshots use SQLite backup(), not raw file copies.
"""
import argparse
import base64
from datetime import datetime, timezone
import getpass
import io
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import zipfile

MAGIC=b'KHB1'

def _fernet(password: str, salt: bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError as error:
        raise RuntimeError('Instale a dependência opcional cryptography (pip install .[backup])') from error
    import hashlib
    key=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,520_000,32)
    return Fernet(base64.urlsafe_b64encode(key))


def _valid(db_path):
    with sqlite3.connect(db_path) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Banco com integridade inválida')
        names={r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
        if not {'projects','contacts','opportunities','tasks','automation_configs'} <= names:
            raise ValueError('Arquivo não contém esquema conhecido do Kelwin Hub')


def backup_db(source:Path, output:Path, password:str):
    if not source.is_file():
        raise ValueError('Banco de origem não encontrado')
    if len(password)<12:
        raise ValueError('Senha do backup deve ter ao menos 12 caracteres')
    if output.exists():
        raise FileExistsError('Backup já existe; escolha outro nome')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        snapshot=Path(t)/'hub.db'
        with sqlite3.connect(source) as db, sqlite3.connect(snapshot) as target:
            db.backup(target)
        _valid(snapshot)
        bytes_buffer=io.BytesIO()
        with zipfile.ZipFile(bytes_buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot,arcname='hub.db')
        salt=secrets.token_bytes(16)
        encrypted=MAGIC+salt+_fernet(password,salt).encrypt(bytes_buffer.getvalue())
        output.write_bytes(encrypted)
        output.chmod(0o600)
    return output


def restore_db(backup:Path, destination:Path, password:str):
    if destination.exists():
        raise FileExistsError('Destino já existe. Restauração nunca sobrescreve arquivos.')
    raw=backup.read_bytes()
    if not raw.startswith(MAGIC) or len(raw)<40:
        raise ValueError('Backup não reconhecido')
    try:
        decoded=_fernet(password,raw[4:20]).decrypt(raw[20:])
    except Exception as ex:
        raise ValueError('Falha de descriptografia: senha incorreta ou backup corrompido') from ex
    with zipfile.ZipFile(io.BytesIO(decoded)) as z:
        file=z.read('hub.db')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as t:
        temp=Path(t.name)
        t.write(file)
    try:
        _valid(temp)
        temp.replace(destination)
        destination.chmod(0o600)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def main():
    parser=argparse.ArgumentParser(description='Backup e restauração cifrados do Kelwin Hub')
    parser.add_argument('action',choices=['backup','restore'])
    parser.add_argument('--db',default='data/hub.db',help='Banco para backup; não usado na restauração')
    parser.add_argument('--file',help='Arquivo .khb de origem/destino')
    parser.add_argument('--target',help='Destino novo para restauração; nunca sobrescreve')
    args=parser.parse_args()
    password=getpass.getpass('Senha de criptografia (mínimo 12 caracteres): ')
    if args.action=='backup':
        output=Path(args.file or f'backups/kelwin-hub-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.khb')
        print('Backup criado:',backup_db(Path(args.db),output,password))
    else:
        if not args.file or not args.target:
            parser.error('Restauração requer --file e --target')
        print('Banco restaurado:',restore_db(Path(args.file),Path(args.target),password))

if __name__=='__main__':
    main()
