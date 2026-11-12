"""Encrypted consistent backup and deliberately non-destructive restore.

Install `pip install '.[backup]'`; snapshots use SQLite backup(), not raw file copies.
"""
import argparse
import base64
from datetime import datetime, timezone
import getpass
import io
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import zipfile

MAGIC = b'KHB1'
# Upper bound applies only to an *unpacked* database on restore; prevent
# attacker-controlled compressed archives from exhausting disk or memory.
MAX_RESTORE_DB_BYTES = 512 * 1024 * 1024


def _fernet(password: str, salt: bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError as error:
        raise RuntimeError('Instale a dependência opcional cryptography (pip install .[backup])') from error
    import hashlib
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 520_000, 32)
    return Fernet(base64.urlsafe_b64encode(key))


def _valid(db_path):
    with sqlite3.connect(db_path) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Banco com integridade inválida')
        names = {r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
        if not {'projects', 'contacts', 'opportunities', 'tasks', 'automation_configs'} <= names:
            raise ValueError('Arquivo não contém esquema conhecido do Kelwin Hub')
        # integrity_check does not report broken referential relationships.
        # Reject corrupted snapshots and restored archives before publication.
        if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Banco com violação de chave estrangeira')


def backup_db(source: Path, output: Path, password: str):
    if not source.is_file():
        raise ValueError('Banco de origem não encontrado')
    if len(password) < 12:
        raise ValueError('Senha do backup deve ter ao menos 12 caracteres')
    if output.exists():
        raise FileExistsError('Backup já existe; escolha outro nome')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        snapshot = Path(t) / 'hub.db'
        with sqlite3.connect(source) as db, sqlite3.connect(snapshot) as target:
            db.backup(target)
        _valid(snapshot)
        bytes_buffer = io.BytesIO()
        with zipfile.ZipFile(bytes_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, arcname='hub.db')
        salt = secrets.token_bytes(16)
        encrypted = MAGIC + salt + _fernet(password, salt).encrypt(bytes_buffer.getvalue())
        # Exclusive creation closes the check-then-write race and keeps contents
        # private from the instant the pathname becomes visible (POSIX mode 0600).
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as result:
                result.write(encrypted)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return output


def restore_db(backup: Path, destination: Path, password: str):
    if destination.exists():
        raise FileExistsError('Destino já existe. Restauração nunca sobrescreve arquivos.')
    if backup.stat().st_size > MAX_RESTORE_DB_BYTES:
        raise ValueError('Backup excede o limite máximo de tamanho')
    raw = backup.read_bytes()
    if not raw.startswith(MAGIC) or len(raw) < 40:
        raise ValueError('Backup não reconhecido')
    try:
        decoded = _fernet(password, raw[4:20]).decrypt(raw[20:])
    except Exception as ex:
        raise ValueError('Falha de descriptografia: senha incorreta ou backup corrompido') from ex
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as t:
        temp = Path(t.name)
    try:
        with zipfile.ZipFile(io.BytesIO(decoded)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != 'hub.db' or members[0].is_dir():
                raise ValueError('Backup não contém um único banco hub.db')
            info = members[0]
            if info.file_size > MAX_RESTORE_DB_BYTES:
                raise ValueError('Banco extraído excederia o limite de tamanho')
            written = 0
            with archive.open(info) as source, temp.open('wb') as target:
                while block := source.read(1024 * 1024):
                    written += len(block)
                    if written > MAX_RESTORE_DB_BYTES:
                        raise ValueError('Banco extraído excederia o limite de tamanho')
                    target.write(block)
            if written != info.file_size:
                raise ValueError('Tamanho do banco extraído não confere')
        _valid(temp)
        # Atomic no-clobber publication. Unlike Path.replace, link() cannot
        # replace a file created after the initial destination.exists() check.
        os.link(temp, destination)
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
