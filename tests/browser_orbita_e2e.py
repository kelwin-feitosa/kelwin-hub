"""Real Chromium + real FastAPI smoke test, using only temporary fictional data.

Run separately from pytest:
  python -m pip install playwright
  python -m playwright install chromium
  python tests/browser_orbita_e2e.py

No actual user database, credentials or external integrations are used.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright
from hub.security import hash_password

PASSWORD = 'Senha-Ficticia-Orbita-2026!'
SIZES = [(320, 760), (360, 740), (390, 844), (768, 900),
         (1024, 768), (1366, 850), (1920, 1080)]
ARTIFACTS = Path('test-artifacts/orbita')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start_server(root, port):
    env = dict(os.environ)
    env.update({
        'HUB_DB_PATH': str(root / 'temporary-orbita.db'),
        'HUB_PASSWORD_HASH': hash_password(PASSWORD),
        'HUB_SESSION_SECRET': 'fictional-session-secret-orbita-2026-strong-key',
        'HUB_SCHEDULER': '0',
    })
    return subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'hub.server:app', '--host', '127.0.0.1',
         '--port', str(port), '--no-access-log'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )


def await_ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('The temporary FastAPI server exited unexpectedly')
        try:
            with urlopen(url + '/healthz', timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            pass
        time.sleep(.2)
    raise TimeoutError('The temporary FastAPI server was not ready')


def run():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kh-orbita-e2e-') as dirname:
        base = Path(dirname)
        port = free_port()
        host = f'http://127.0.0.1:{port}'
        proc = start_server(base, port)
        try:
            await_ready(host, proc)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1366, 'height': 850},
                                        device_scale_factor=1, locale='pt-BR')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(host, wait_until='domcontentloaded')
                expect(page.locator('#login-screen')).to_be_visible()
                page.locator('#password').fill(PASSWORD)
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#shell')).to_be_visible()
                expect(page.locator('#pageTitle')).to_contain_text('Mesa')
                # Explore provides all modules without adding permanent nav items.
                page.locator('#nav [data-tab=explore]').click()
                expect(page.locator('#pageTitle')).to_have_text('Explorar')
                expect(page.locator('.orbit-explore-entry')).to_have_count(8)
                page.screenshot(path=str(ARTIFACTS / 'explore-desktop-light.png'), full_page=True)
                page.locator('.orbit-explore-entry[data-tab=tasks]').click()
                expect(page.locator('#pageTitle')).to_have_text('Tarefas')
                # Create a project using the same action search used for records.
                page.locator('#create-open').click()
                expect(page.locator('#search-dialog')).to_be_visible()
                page.locator('#search-results button[data-do=add-project]').click()
                expect(page.locator('#dialog')).to_be_visible()
                page.locator('#f_name').fill('Projeto fictício ÓRBITA')
                page.locator('#f_area').fill('Teste de navegação')
                page.locator('#dynamic-form button[type=submit]').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                page.locator('#nav [data-tab=projects]').click()
                expect(page.get_by_text('Projeto fictício ÓRBITA')).to_be_visible()
                # Create a linked task; verify persistence through the real API.
                page.locator('#create-open').click()
                page.locator('#search-results button[data-do=add-task]').click()
                page.locator('#f_title').fill('Tarefa fictícia ÓRBITA')
                page.locator('#f_project_id').select_option(label='Projeto fictício ÓRBITA')
                page.locator('#dynamic-form button[type=submit]').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                page.locator('#search-open').click()
                page.locator('#search-query').fill('Tarefa fictícia')
                expect(page.locator('#search-results .search-result')).not_to_have_count(0)
                page.locator('#search-results .search-result[data-tab=tasks]').first.click()
                expect(page.locator('#content').get_by_text('Tarefa fictícia ÓRBITA')).to_be_visible()
                page.locator('#theme').click()
                assert page.locator('html').get_attribute('data-theme') == 'dark'
                page.locator('#nav [data-tab=explore]').click()
                page.screenshot(path=str(ARTIFACTS / 'explore-desktop-dark.png'), full_page=True)
                for width, height in SIZES:
                    page.set_viewport_size({'width': width, 'height': height})
                    page.locator('#nav [data-tab=explore]').click()
                    expect(page.locator('.orbit-explore-entry')).to_have_count(8)
                    overflow = page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
                    assert overflow <= 2, f'Horizontal page overflow at {width}px: {overflow}px'
                    if width < 700:
                        pos = page.locator('#nav').evaluate('(e)=>getComputedStyle(e).position')
                        assert pos == 'fixed', f'Mobile navigation not fixed at {width}px: {pos}'
                        page.locator('.orbit-explore-entry[data-tab=automations]').click()
                        expect(page.locator('#pageTitle')).to_have_text('Automações')
                        page.locator('#nav [data-tab=explore]').click()
                    if width in (320, 390, 768, 1366, 1920):
                        page.screenshot(path=str(ARTIFACTS / f'explore-{width}-dark.png'), full_page=True)
                # No JS exceptions while navigating, creating and changing theme.
                assert not errors, f'Browser errors: {errors}'
                browser.close()
            print('ORBITA real browser E2E passed (temporary FastAPI + SQLite; 7 viewports).')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == '__main__':
    run()
