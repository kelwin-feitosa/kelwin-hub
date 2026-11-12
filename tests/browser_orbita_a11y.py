"""axe-core WCAG checks against real local FastAPI + Chromium with fictional data.

The axe script is intercepted as a same-origin resource; this preserves CSP.
No real user records or external analytics are used.
"""
from pathlib import Path
import tempfile
from playwright.sync_api import expect, sync_playwright
from browser_orbita_e2e import PASSWORD, free_port, start_server, await_ready

AXE = Path('node_modules/axe-core/axe.min.js')
TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']


def run():
    assert AXE.is_file(), 'Install axe-core in CI before this check'
    source = AXE.read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='kh-orbita-accessibility-') as dirname:
        root = Path(dirname)
        port = free_port()
        server = start_server(root, port)
        origin = f'http://127.0.0.1:{port}'
        try:
            await_ready(origin, server)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1366, 'height': 850}, locale='pt-BR')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route(origin + '/static/axe.min.js', lambda route: route.fulfill(
                    status=200, content_type='application/javascript', body=source))
                page.goto(origin, wait_until='domcontentloaded')
                expect(page.locator('#login-screen')).to_be_visible()
                page.add_script_tag(url=origin + '/static/axe.min.js')

                def check(label):
                    result = page.evaluate('''async (tags) =>
                        await window.axe.run(document, {runOnly: {type: 'tag', values: tags}})
                    ''', TAGS)
                    violations = result['violations']
                    for violation in violations:
                        targets = [node['target'] for node in violation['nodes'][:4]]
                        print(f"{label}: {violation['id']} [{violation['impact']}] -> {targets}")
                    assert not violations, f'axe-core WCAG A/AA violations in {label}: {len(violations)}'
                    print(f"{label}: WCAG A/AA axe-core checks passed ({len(result['passes'])} rules)")

                check('Login desktop')
                page.locator('#password').fill(PASSWORD)
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#shell')).to_be_visible()
                page.locator('#nav [data-tab=explore]').click()
                check('Explore desktop light')
                page.locator('#search-open').click()
                expect(page.locator('#search-dialog')).to_be_visible()
                check('Search dialog')
                page.locator('#search-close').click()
                page.locator('#create-open').click()
                page.locator('#search-results button[data-do=add-project]').click()
                expect(page.locator('#dialog')).to_be_visible()
                check('Create project form')
                page.locator('#cancel-dialog').click()
                page.locator('#theme').click()
                page.set_viewport_size({'width': 390, 'height': 844})
                page.locator('#nav [data-tab=explore]').click()
                check('Explore mobile dark')
                assert not errors, f'Browser JavaScript errors: {errors}'
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except Exception:
                server.kill()
                server.wait(timeout=5)


if __name__ == '__main__':
    run()
