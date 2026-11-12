"""Optional real-Chromium UI smoke (mocked API, not an end-to-end server check)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':390,'height':844})
        page.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body><div id="toast"></div></body></html>')
        page.add_style_tag(path=str(ROOT/'hub/static/app.css'))
        page.add_style_tag(path=str(ROOT/'hub/static/meeting-review.css'))
        page.add_style_tag(path=str(ROOT/'hub/static/availability-ui.css'))
        page.evaluate('''() => {
           window.notify=(s)=>{window.lastNotify=s};
           window.showTab=async()=>{};
           window.requests=[];
           window.api=async(url,method='GET',data)=>{
             window.requests.push({url,method,data});
             if(url==='/api/projects')return [{id:'proj-1',name:'Projeto fictício'}];
             if(url.includes('/analyses')&&method==='GET')return [{id:'analysis-1',summary:'Análise fictícia',items:[
               {id:'item-1',kind:'action',title:'Revisar projeto',detail:'Ação fictícia',evidence_quote:'Vamos revisar o projeto.',status:'proposed'}]}];
             if(url==='/api/availability/windows'&&method==='GET')return [{id:'window-1',weekday:2,start_time:'09:00',end_time:'11:00'}];
             if(url.startsWith('/api/availability/slots'))return {slots:[{start_at:'2027-01-06T12:00:00+00:00',end_at:'2027-01-06T12:30:00+00:00'}]};
             return {ok:true};
           };
        }''')
        page.add_script_tag(path=str(ROOT/'hub/static/meeting-review.js'))
        page.add_script_tag(path=str(ROOT/'hub/static/availability-ui.js'))
        page.evaluate("window.KelwinReview.open('tr-1')")
        page.get_by_role('button',name='Aprovar e criar tarefa').click()
        assert page.evaluate("window.requests.some(x=>x.url.endsWith('/convert') && x.method==='POST')")
        page.get_by_role('button',name='Fechar').first.click()
        page.evaluate('window.KelwinAvailability.open()')
        page.get_by_role('button',name='Mostrar horários').click()
        page.locator('#availability-event-title').fill('Reunião fictícia')
        page.get_by_role('button',name='09:00–09:30').click()
        assert page.evaluate("window.requests.some(x=>x.url==='/api/events' && x.method==='POST')")
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        Path('/mnt/data/hub13-ui-mock.png').parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path='/mnt/data/hub13-ui-mock.png')
        browser.close()
        print('CHROMIUM MOCK UI: revisão, aprovação, disponibilidade, evento e layout mobile: OK')

if __name__=='__main__':main()
