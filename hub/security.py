"""Autenticação de usuário único; segredos somente no servidor."""
import base64
import hashlib
import hmac
import secrets
import time

ITERATIONS = 430_000
SESSION_SECONDS = 12 * 60 * 60


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError('Use uma senha de pelo menos 12 caracteres')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'pbkdf2_sha256:{ITERATIONS}:{_b64(salt)}:{_b64(digest)}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, count, salt, digest = encoded.split(':')
        if algorithm != 'pbkdf2_sha256' or not 100_000 <= int(count) <= 1_000_000:
            return False
        computed = hashlib.pbkdf2_hmac('sha256', password.encode(), _unb64(salt), int(count))
        return hmac.compare_digest(computed, _unb64(digest))
    except (ValueError, TypeError, IndexError):
        return False


def sign_session(secret: str) -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    data = f'{timestamp}.{nonce}'
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f'{data}.{signature}'


def validate_session(secret: str, cookie: str | None) -> str | None:
    if not cookie:
        return None
    try:
        timestamp, nonce, signature = cookie.split('.')
        ts = int(timestamp)
        now = int(time.time())
        if ts > now + 60 or now - ts > SESSION_SECONDS:
            return None
        data = f'{timestamp}.{nonce}'
        expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected):
            return nonce
    except (ValueError, AttributeError):
        return None
    return None


def csrf_token(secret: str, nonce: str) -> str:
    return hmac.new(secret.encode(), f'csrf:{nonce}'.encode(), hashlib.sha256).hexdigest()
