"""NEXO end-to-end with real Chromium/FastAPI and isolated synthetic SQLite."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_orbita_e2e import PASSWORD, free_port, start_server, await_ready


def run():
    with tempfile.TemporaryDirectory(prefix='kh-nexo-e2e-') as dirname:
        port = free_port()
        host = f'http://127.0.0.1:{port}'
        server = start_server(Path(dirname), port)
        try:
            await_ready(host, server)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width':1366,'height':850},locale='pt-BR')
                browser_errors=[]
                requests=[]
                page.on('pageerror', lambda error: browser_errors.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))
                page.goto(host, wait_until='domcontentloaded')
                page.locator('#password').fill(PASSWORD)
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#shell')).to_be_visible()
                csrf = page.request.get(host + '/api/session').json()['csrf']
                headers={'X-CSRF-Token':csrf}

                def post(endpoint, data):
                    response=page.request.post(host+endpoint, headers=headers, data=data)
                    assert response.status==201, (endpoint,response.status,response.text())
                    return response.json()['id']

                project=post('/api/projects',{'name':'Projeto NEXO fictício','area':'Teste'})
                post('/api/notes',{'title':'Notas vinculadas','body':'Resumo da reunião local','project_id':project})
                post('/api/events',{'title':'Compromisso NEXO','status':'proposed',
                    'start_at':'2027-01-15T14:00:00Z','end_at':'2027-01-15T14:30:00Z','project_id':project})
                contact=post('/api/contacts',{'name':'Cliente fictício'})
                opportunity=post('/api/opportunities',{'contact_id':contact,
                    'title':'Contrato NEXO de teste','next_action':'Enviar proposta'})
                post('/api/notes',{'title':'Nota da oportunidade','body':'Contexto autorizado','opportunity_id':opportunity})
                post('/api/tasks',{'title':'Ação comercial vinculada','opportunity_id':opportunity})

                page.locator('#nav [data-tab=projects]').click()
                expect(page.locator('#pageTitle')).to_have_text('Projetos')
                requests.clear()
                page.locator(f'#projects-item-{project} [data-do=project-context]').click()
                project_context=page.locator(f'#project-context-{project}')
                expect(project_context).to_contain_text('Notas vinculadas')
                expect(project_context).to_contain_text('Compromisso NEXO')
                context_calls=[url for url in requests if '/api/projects/' in url and '/context' in url]
                assert len(context_calls)==1, context_calls
                assert not [url for url in requests if url.endswith('/api/events')], 'Project fetched all events'

                page.locator('#nav [data-tab=explore]').click()
                page.locator('.orbit-explore-entry[data-tab=opportunities]').click()
                expect(page.locator('#pageTitle')).to_have_text('Oportunidades')
                page.locator(f'#opportunities-item-{opportunity} [data-do=opportunity-context]').click()
                detail=page.locator(f'#opportunity-context-{opportunity}')
                expect(detail).to_contain_text('Nota da oportunidade')
                expect(detail).to_contain_text('Ação comercial vinculada')
                detail.locator('[data-do=add-opportunity-note]').click()
                expect(page.locator('#dialog')).to_be_visible()
                assert page.locator('#f_opportunity_id').input_value()==opportunity
                page.locator('#f_title').fill('Nova nota contextual')
                page.locator('#f_body').fill('Texto registrado no contexto atual')
                page.locator('#dynamic-form button[type=submit]').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                expect(detail).to_contain_text('Nova nota contextual')
                detail.locator('[data-do=add-linked-task]').click()
                expect(page.locator('#dialog')).to_be_visible()
                page.locator('#f_title').fill('Nova tarefa contextual')
                page.locator('#dynamic-form button[type=submit]').click()
                expect(page.locator('#dialog')).not_to_be_visible()
                expect(detail).to_contain_text('Nova tarefa contextual')
                stored=page.request.get(host+'/api/tasks').json()
                assert any(x['title']=='Nova tarefa contextual' and x['opportunity_id']==opportunity for x in stored)

                page.locator('#nav [data-tab=today]').click()
                expect(page.locator('.nexo-recent')).to_contain_text('Contrato NEXO de teste')
                page.locator(f'[data-nexo-kind=opportunities][data-nexo-id="{opportunity}"]').click()
                expect(page.locator(f'#opportunity-context-{opportunity}')).to_be_visible()

                page.set_viewport_size({'width':390,'height':844})
                # Wait for responsive reflow to settle after the viewport changes.
                # A persistent overflow still fails, rather than being masked by CSS clipping.
                page.wait_for_function('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2', timeout=3000)
                overflow=page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')
                offenders=page.evaluate("""() => [...document.querySelectorAll('body *')].map(e => ({name:e.tagName,className:String(e.className).slice(0,80),id:e.id,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width})).filter(e=>e.right>innerWidth+2 && e.width>1).slice(0,15)""")
                if overflow > 2:
                    Path('test-artifacts/orbita').mkdir(parents=True, exist_ok=True)
                    page.screenshot(path='test-artifacts/orbita/nexo-mobile-overflow.png',full_page=True)
                metrics=page.evaluate("""() => Object.fromEntries(['html','body','.shell','.main-wrap','.topbar','.top-actions','#content','.opportunity-board','.nexo-opportunity'].map(s=>{const e=document.querySelector(s);return [s,e&&{scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,rectWidth:e.getBoundingClientRect().width,rectRight:e.getBoundingClientRect().right}]}))""")
                assert overflow <= 2, (overflow, metrics, offenders)
                page.locator('#nav [data-tab=projects]').click()
                page.locator(f'#projects-item-{project} [data-do=project-context]').click()
                expect(page.locator(f'#project-context-{project}')).to_contain_text('Notas vinculadas')
                assert page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth') <= 2
                assert not browser_errors, browser_errors
                browser.close()
            print('NEXO real browser E2E passed: project/opportunity context, linked capture, resume, mobile.')
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except Exception:
                server.kill()
                server.wait(timeout=5)


if __name__=='__main__':
    run()