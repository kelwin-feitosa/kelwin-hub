"""Real-browser regression for unsaved form edits and duplicate submissions."""
import tempfile
import sqlite3
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
                # Bounded task UI: real API records, next page and literal search.
                csrf = page.request.get(host + '/api/session').json()['csrf']
                for index in range(35):
                    response = page.request.post(
                        host + '/api/tasks', headers={'X-CSRF-Token': csrf},
                        data={'title': f'Tarefa fictícia {index:02d}', **({'estimated_minutes': 15} if index == 0 else {})})
                    assert response.status == 201, response.text()
                page.locator('#nav [data-tab=explore]').click()
                page.locator('.orbit-explore-entry[data-tab=tasks]').click()
                expect(page.locator('[id^="tasks-item-"]')).to_have_count(30)
                expect(page.locator('.task-pagination')).to_contain_text('Página 1 de 2')
                page.locator('[data-do=task-next]').click()
                expect(page.locator('[id^="tasks-item-"]')).to_have_count(5)
                expect(page.locator('.task-pagination')).to_contain_text('Página 2 de 2')
                page.locator('#task-query').fill('fictícia 34')
                page.locator('#tasks-filter-form button[type=submit]').click()
                expect(page.locator('[id^="tasks-item-"]')).to_have_count(1)
                assert page.evaluate(
                    'document.documentElement.scrollWidth - document.documentElement.clientWidth'
                ) <= 2, 'Task filters overflow on mobile viewport'
                page.locator('[data-do=task-clear]').click()
                expect(page.locator('[id^="tasks-item-"]')).to_have_count(30)
                # Explicit personal 15-minute estimate is the only suggested task.
                page.locator('#nav [data-tab=today]').click()
                expect(page.locator('#focus-form')).to_be_visible()
                page.locator('#focus-minutes').select_option('15')
                page.locator('#focus-form button[type=submit]').click()
                expect(page.locator('.focus-item')).to_have_count(1)
                expect(page.locator('.focus-item')).to_contain_text('Tarefa fictícia 00')
                page.locator('.focus-item [data-do=edit-task]').click()
                expect(page.locator('#f_estimated_minutes')).to_have_value('15')
                page.locator('#cancel-dialog').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                # H17-01: Mesa presents exact counts and progressively reveals all 35 actions.
                page.locator('#nav [data-tab=today]').click()
                expect(page.locator('[data-workspace-group=next] .work-counter')).to_have_text('35')
                expect(page.locator('[data-workspace-group=next] .work-entry')).to_have_count(12)
                expect(page.locator('[data-workspace-group=next] [data-do=workspace-more]')).to_contain_text('23 restantes')
                page.locator('[data-workspace-group=next] [data-do=workspace-more]').click()
                expect(page.locator('[data-workspace-group=next] .work-entry')).to_have_count(35)
                expect(page.locator('[data-workspace-group=next] [data-do=workspace-more]')).to_have_count(0)
                assert page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth') <= 2
                # H17-03/13: prove an old note remains navigable beyond page 1.
                with sqlite3.connect(str(Path(dirname)/'temporary-orbita.db')) as db:
                    db.executemany(
                        'INSERT INTO notes (id,title,body,project_id,contact_id,opportunity_id,created_at,updated_at) VALUES (?,?,?,NULL,NULL,NULL,?,?)',
                        [(f'note-{i:03d}',
                          'Nota especial fora da primeira página' if i == 0 else f'Nota regular {i:03d}',
                          'Conteúdo fictício',
                          '2025-01-01T00:00:00+00:00',
                          '2025-01-01T00:00:00+00:00' if i == 0 else '2026-11-17T12:00:00+00:00')
                         for i in range(121)])
                page.locator('#nav [data-tab=explore]').click()
                page.locator('.orbit-explore-entry[data-tab=notes]').click()
                expect(page.locator('[id^="notes-item-"]')).to_have_count(30)
                expect(page.locator('nav[aria-label="Páginas de notas"]')).to_contain_text('Página 1 de 5')
                for _ in range(4):
                    page.locator('[data-do=note-next]').click()
                expect(page.locator('[id^="notes-item-"]')).to_have_count(1)
                expect(page.locator('#notes-item-note-000')).to_be_visible()
                # A global search result points to its exact ID, not the first 100.
                page.keyboard.press('Control+k')
                expect(page.locator('#search-dialog')).to_be_visible()
                page.locator('#search-query').fill('Nota especial fora da primeira página')
                expect(page.locator('#search-results button[data-tab=notes]')).to_have_count(1)
                page.locator('#search-results button[data-tab=notes]').click()
                expect(page.locator('#notes-item-note-000')).to_be_visible()
                page.locator('#notes-item-note-000 [data-do=edit-note]').click()
                expect(page.locator('#f_title')).to_have_value('Nota especial fora da primeira página')
                page.locator('#f_title').fill('Nota antiga realmente editada')
                page.locator('#dynamic-form button[type=submit]').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                note=page.request.get(host+'/api/notes/note-000').json()
                assert note['title']=='Nota antiga realmente editada', note
                assert page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth') <= 2
                # H17-04: delayed success from a previous tab must never replace Explorar.
                page.evaluate("""() => {
                  const real = window.fetch.bind(window);
                  window.__originalFetch18 = real;
                  window.fetch = (input,opts) => {
                    if (String(input) !== '/api/projects') return real(input,opts);
                    return new Promise((resolve,reject) => {
                      window.__releaseProjects18=()=>real(input,opts).then(resolve,reject);
                      window.__rejectProjects18=()=>reject(new Error('Network test failure'));
                    });
                  };
                }""")
                page.locator('#nav [data-tab=projects]').click()
                page.wait_for_function('typeof window.__releaseProjects18 === "function"')
                page.locator('#nav [data-tab=explore]').click()
                expect(page.locator('.orbit-explore-entry')).to_have_count(8)
                page.evaluate('window.__releaseProjects18()')
                page.wait_for_timeout(250)
                expect(page.locator('#pageTitle')).to_have_text('Explorar')
                expect(page.locator('.orbit-explore-entry')).to_have_count(8)
                # A delayed error from another tab must not create an error page.
                page.evaluate('window.__rejectProjects18=null')
                page.locator('#nav [data-tab=projects]').click()
                page.wait_for_function('typeof window.__rejectProjects18 === "function"')
                page.locator('#nav [data-tab=explore]').click()
                page.evaluate('window.__rejectProjects18()')
                page.wait_for_timeout(250)
                expect(page.locator('#pageTitle')).to_have_text('Explorar')
                expect(page.locator('.orbit-explore-entry')).to_have_count(8)
                page.evaluate('window.fetch=window.__originalFetch18')
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
