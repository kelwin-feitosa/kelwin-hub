// Minimal no-browser semantic checks on the same production frontend implementation.
// Not a substitute for Playwright/manual navigation or WCAG verification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'hub/static/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'hub/static/index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'hub/static/app.css'), 'utf8');
const view = {innerHTML: ''};
const ctx = vm.createContext({
  document: {getElementById(id) {return id === 'content' ? view : null;}},
  window: {addEventListener() {}},
  console, setTimeout() {}, clearTimeout() {},
});
vm.runInContext(source, ctx, {filename: 'app.js'});
const bad = '<img src=x onerror=alert(1)>';
const row = vm.runInContext(`workRow(${JSON.stringify({
  kind: 'task', id: 'id-1', title: bad, project_id: 'p', project_name: bad,
  opportunity_id: 'o', opportunity_title: 'Cliente', contact_name: 'Teste',
  due_at: null, next_action: 'Revisar', status: 'open', priority: 2,
})})`, ctx);
assert(!row.includes(bad), 'Dynamic field should never be inserted as HTML');
assert(row.includes('&lt;img'), 'Title must be HTML-escaped');
assert(row.includes('data-do="open-project"'));
assert(row.includes('data-do="open-opportunity"'));
assert(row.includes('data-do="complete"'));
const opp = vm.runInContext(`workRow(${JSON.stringify({
  kind: 'opportunity', id: 'op', title: 'Reunião', contact_name: 'Contato',
  next_action: 'Ligar', due_at: null, priority: 1,
})})`, ctx);
assert(opp.includes('data-do="add-linked-task"'));
assert(opp.includes('data-do="contacted"'));
assert(html.includes('data-tab="today"'));
assert(html.includes('id="nav"'));
assert(css.includes('prefers-reduced-motion'));
vm.runInContext(`api = async function(url) {
 if(url === '/api/workspace') return {
  local_date:'2026-11-11',groups:{now:[],next:[{kind:'opportunity',id:'op',title:'Teste',next_action:'Ligar',due_at:null,priority:1}],later:[],blocked:[]},events:[],alerts:[]};
 if(url === '/api/projects') return [{id:'project-1',name:'Projeto',status:'active'}];
 if(url === '/api/nexo/suggestions') return [];
 throw Error('Unexpected API ' + url);
}`, ctx);
(async () => {
 await vm.runInContext('todayView()', ctx);
 assert(view.innerHTML.includes('id="quick-task"'));
 assert(view.innerHTML.includes('data-do="add-linked-task"'));
 assert(view.innerHTML.includes('Precisa de atenção'));
 assert(view.innerHTML.includes('Projeto'));
 assert(!view.innerHTML.includes('class="stats"'), 'No generic counter grid on the Mesa');
 console.log('UI semantic checks passed (browser verification remains pending).');
})().catch(e => {console.error(e); process.exitCode=1;});
