"""Optional authentic browser ↔ FastAPI smoke test, uses synthetic data only.

Run: python tests/browser_live_smoke.py
Requires chromium and playwright; deliberately not a CI dependency.
"""
import multiprocessing
import sys
sys.path.insert(0,str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import socket
import tempfile
import time
from pathlib import Path

import uvicorn
from hub.api import create_app
from hub.security import hash_password
from playwright.sync_api import sync_playwright


def serve(db, port):
    app=create_app(db,password_hash=hash_password('Browser-test-password-2026!'),
                   session_secret='A'*48,scheduler=False)
    uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')


def main():
    with tempfile.TemporaryDirectory() as td:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        proc=multiprocessing.Process(target=serve,args=(str(Path(td)/'hub.db'),port),daemon=True)
        proc.start()
        try:
            import urllib.request
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.3) as r:
                        if r.status==200:break
                except Exception:time.sleep(.08)
            else:raise RuntimeError('FastAPI did not start')
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':390,'height':844})
                errors=[]
                page.on('pageerror',lambda err: errors.append(str(err)))
                page.goto(f'http://127.0.0.1:{port}/',wait_until='domcontentloaded',timeout=10000)
                page.locator('#password').fill('Browser-test-password-2026!')
                page.get_by_role('button',name='Entrar no Kelwin Hub').click()
                page.get_by_role('button',name='Projetos',exact=True).click()
                page.get_by_role('button',name='Novo projeto').click()
                page.locator('#f_name').fill('Projeto de validação')
                page.locator('#f_area').fill('estudos')
                page.locator('#dynamic-form button[type=submit]').click()
                page.locator('[data-do="project-context"]').first.click()
                page.locator('[data-do="add-project-note"]').first.click()
                page.locator('#f_title').fill('Nota do teste')
                page.locator('#f_body').fill('Conteúdo sobre pesquisa MusicXML')
                page.locator('#dynamic-form button[type=submit]').click()
                page.get_by_text('Nota do teste').first.wait_for()
                page.locator('#search-open').click()
                page.locator('#search-query').fill('MusicXML')
                page.locator('#search-results .search-result').first.wait_for()
                page.locator('#search-results .search-result').first.click()
                page.get_by_text('Nota do teste').first.wait_for()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(Path(td)/'hub12-mobile.png'))
                assert not errors,errors
                browser.close()
                print('BROWSER REAL: login + projeto + nota vinculada + busca + navegação mobile: OK')
        finally:
            proc.terminate();proc.join(timeout=4)

if __name__=='__main__':main()
