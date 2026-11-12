"""Regression for user feedback: local icon and neutral dark palette."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from hub.api import create_app
from hub.security import hash_password

ROOT = Path(__file__).resolve().parents[1]


def test_favicon_is_served_from_root_without_auth(tmp_path):
    app = create_app(str(tmp_path / 'data.db'), password_hash=hash_password('fictitious-password-123'),
                     session_secret='testing-only-' * 5, scheduler=False)
    with TestClient(app) as client:
        response = client.get('/favicon.ico')
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('image/svg+xml')
        assert b'<svg' in response.content
        assert response.headers['x-content-type-options'] == 'nosniff'
        page = client.get('/')
        assert 'href="/favicon.ico"' in page.text


def test_dark_tokens_are_neutral_and_semantic():
    css = (ROOT / 'hub/static/app.css').read_text(encoding='utf-8')
    dark = re.search(r':root\[data-theme="dark"\]\s*\{([^}]+)\}', css)
    assert dark
    for key in ('--bg', '--panel', '--panel2', '--text', '--muted', '--border', '--accent', '--on-accent', '--focus'):
        assert f'{key}:' in dark.group(1)
    for key in ('--bg', '--panel', '--panel2'):
        value = re.search(rf'{key}:(#[0-9a-f]{{6}})', dark.group(1)).group(1)
        rgb = [int(value[j:j + 2], 16) for j in (1, 3, 5)]
        # Neutral/slate backgrounds: no green color cast.
        assert rgb[1] <= rgb[2]
    assert '#8be0bd' not in css
    assert 'prefers-reduced-motion:reduce' in css


def test_theme_respects_system_preference_unless_saved():
    js = (ROOT / 'hub/static/app.js').read_text(encoding='utf-8')
    assert 'prefers-color-scheme: dark' in js
    assert "localStorage.getItem('kh_theme')" in js
