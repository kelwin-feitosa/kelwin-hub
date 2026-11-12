"""Non-destructive preflight for a local Kelwin Hub installation.

Checks existing configuration and SQLite integrity without applying migrations or
opening the database in read/write mode. Stop the server before running.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import stat
from urllib.parse import quote

from hub.storage import LATEST_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = {'HUB_PASSWORD_HASH', 'HUB_SESSION_SECRET'}
REQUIRED_TABLES = {'projects', 'tasks', 'contacts', 'opportunities', 'automation_configs'}


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def inspect_installation(config: Path, database: Path | None = None) -> dict:
    """Return only structural findings; never return secret values or user records."""
    errors, warnings = [], []
    config = Path(config)
    values = {}
    if not config.is_file():
        errors.append('Configuração .env não encontrada; configure a instalação primeiro')
    else:
        if config.is_symlink():
            errors.append('Configuração .env não deve ser um link simbólico')
        elif os.name == 'posix' and stat.S_IMODE(config.stat().st_mode) & 0o077:
            warnings.append('.env acessível por outros usuários; ajuste para chmod 600')
        try:
            values = read_env(config)
        except (OSError, UnicodeError) as exc:
            errors.append('Não foi possível ler a configuração: ' + type(exc).__name__)
        missing = sorted(key for key in REQUIRED_ENV if not values.get(key))
        if missing:
            errors.append('Configuração incompleta: ' + ', '.join(missing))
    raw_db = database if database is not None else Path(values.get('HUB_DB_PATH') or './data/hub.db')
    db_path = Path(raw_db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    result = {'status': 'ok', 'schema_version': None, 'expected_schema_version': LATEST_SCHEMA_VERSION,
              'errors': errors, 'warnings': warnings}
    if db_path.is_symlink():
        errors.append('Banco de dados não deve ser um link simbólico')
    elif not db_path.is_file():
        errors.append('Banco ainda não encontrado; confirme o caminho antes de atualizar')
    else:
        if os.name == 'posix' and stat.S_IMODE(db_path.stat().st_mode) & 0o077:
            warnings.append('Banco acessível por outros usuários; reinicie com Hub atualizado para restringir permissões')
        try:
            # URI read-only mode rejects missing DBs instead of creating one.
            uri = 'file:' + quote(str(db_path.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=3)) as db:
                db.execute('PRAGMA query_only=ON')
                version = db.execute('PRAGMA user_version').fetchone()[0]
                result['schema_version'] = version
                if version > LATEST_SCHEMA_VERSION:
                    errors.append('Banco usa esquema mais recente que a aplicação')
                elif version < LATEST_SCHEMA_VERSION:
                    warnings.append('Migrações pendentes; faça backup antes da atualização')
                integrity = db.execute('PRAGMA integrity_check').fetchone()
                if not integrity or integrity[0] != 'ok':
                    errors.append('Falha no integrity_check do SQLite')
                if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    errors.append('Falha no foreign_key_check do SQLite')
                table_names = {r[0] for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not REQUIRED_TABLES.issubset(table_names):
                    errors.append('Tabelas essenciais ausentes no banco')
        except sqlite3.Error as exc:
            errors.append('Não foi possível validar SQLite: ' + type(exc).__name__)
    if errors:
        result['status'] = 'error'
    elif warnings:
        result['status'] = 'warning'
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnóstico local e sem escrita antes da atualização')
    parser.add_argument('--env', type=Path, default=ROOT / '.env')
    parser.add_argument('--db', type=Path, default=None)
    args = parser.parse_args()
    result = inspect_installation(args.env, args.db)
    print('Estado:', result['status'])
    print('Versão do esquema:', result['schema_version'], '/', result['expected_schema_version'])
    for finding in result['warnings']:
        print('AVISO:', finding)
    for finding in result['errors']:
        print('ERRO:', finding)
    if result['status'] == 'ok':
        print('Diagnóstico aprovado. Ainda é necessário backup e validação de atualização.')
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
