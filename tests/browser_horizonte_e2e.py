"""Real-browser regression for unsaved form edits and duplicate submissions."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_orbita_e2e import PASSWORD, free_port, start_server, await_ready


def run():
    with tempfile.TemporaryDirectory(prefix='kh-horizonte-e2e-') as dirname:
        port = free_port()
        host = f'http://127.0.0.1:{port}'
        server = start_server(Path(dirname), port)
        try:
            await_ready(host, server)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 390, 'height': 844}, locale='pt-BR')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(host, wait_until='domcontentloaded')
                page.locator('#password').fill(PASSWORD)
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#shell')).to_be_visible()

                def open_project_form():
                    page.locator('#create-open').click()
                    expect(page.locator('#search-dialog')).to_be_visible()
                    page.locator('#search-results button[data-do=add-project]').click()
                    expect(page.locator('#dialog')).to_be_visible()

                open_project_form()
                page.locator('#f_name').fill('Rascunho não salvo')
                page.once('dialog', lambda dialog: dialog.dismiss())
                page.keyboard.press('Escape')
                expect(page.locator('#dialog')).to_be_visible()
                assert page.locator('#f_name').input_value() == 'Rascunho não salvo'

                page.once('dialog', lambda dialog: dialog.dismiss())
                page.locator('#cancel-dialog').click()
                expect(page.locator('#dialog')).to_be_visible()
                page.once('dialog', lambda dialog: dialog.accept())
                page.locator('#cancel-dialog').click()
                expect(page.locator('#dialog')).not_to_be_visible()

                open_project_form()
                page.locator('#f_name').fill('Projeto único após duplo clique')
                page.locator('#f_area').fill('Teste integrado')
                # Two clicks during one JS task exercise the real submission guard
                # before the first network response resolves.
                page.evaluate("""() => {
                    const save = document.querySelector('#dynamic-form button[type=submit]');
                    save.click();
                    save.click();
                }""")
                expect(page.locator('#dialog')).not_to_be_visible()
                projects = page.request.get(host + '/api/projects').json()
                assert sum(1 for p in projects
                           if p['name'] == 'Projeto único após duplo clique') == 1, projects
                assert not errors, errors
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except Exception:
                server.kill()
                server.wait(timeout=8)


if __name__ == '__main__':
    run()
