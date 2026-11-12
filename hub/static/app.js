'use strict';
const $=(id)=>document.getElementById(id);
const safe=(v)=>String(v??'').replace(/[&<>"']/g,(x)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const dateTime=(v)=>v?new Date(v).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'Sem data';
const localInputValue=(value)=>{const d=new Date(value);const local=new Date(d.getTime()-d.getTimezoneOffset()*60000);return local.toISOString().slice(0,16)};
let csrf=null,tab='today',toastTimeout;
const tabs={today:'Mesa de trabalho',tasks:'Tarefas',projects:'Projetos',contacts:'Contatos',opportunities:'Oportunidades',events:'Agenda',notes:'Notas',automations:'Automações',explore:'Explorar'};
function notify(message){const el=$('toast');el.textContent=message;el.classList.add('show');clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>el.classList.remove('show'),3300)}
async function api(url,method='GET',data){
 const headers={'Accept':'application/json'};
 if(method!=='GET'){headers['Content-Type']='application/json';if(csrf)headers['X-CSRF-Token']=csrf}
 const resp=await fetch(url,{method,headers,body:data===undefined?undefined:JSON.stringify(data),credentials:'same-origin'});
 const body=await resp.json().catch(()=>({}));
 if(resp.status===401&&url!=='/api/login'){await showAuth();throw Error('Sessão expirada')}
 if(!resp.ok){let detail=body.detail;if(Array.isArray(detail))detail=detail.map(x=>x.msg).join('; ');throw Error(detail||`Erro HTTP ${resp.status}`)}
 return body;
}
async function showAuth(){csrf=null;$('shell').hidden=true;$('login-screen').hidden=false;$('password').value='';}
async function showApp(){const state=await api('/api/session');if(!state.authenticated){showAuth();return}csrf=state.csrf;$('shell').hidden=false;$('login-screen').hidden=true;await showTab('today')}
function changeTheme(){const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;(()=>{try{localStorage.setItem('kh_theme',next)}catch(_){/* storage may be disabled */}})()}
let searchSequence=0,searchTimer=null,searchPreviousFocus=null;
function openSearch(){
 if($('shell').hidden||$('search-dialog').open)return;
 searchPreviousFocus=document.activeElement;
 $('search-query').value='';
 $('search-results').innerHTML='<p class="muted">Digite para encontrar registros.</p>';
 $('search-dialog').showModal();window.KelwinNav?.showSuggestions();$('search-query').focus();
}
function searchResult(item){
 const kind={projects:'Projeto',tasks:'Tarefa',contacts:'Contato',opportunities:'Oportunidade',events:'Agenda',notes:'Nota'}[item.kind]||'Registro';
 return `<button type="button" class="search-result" data-tab="${safe(item.kind)}" data-id="${safe(item.id)}"><span class="search-result-kind">${kind}</span><strong>${safe(item.title)}</strong><small>${safe(item.detail)}${item.status?' · '+safe(item.status):''}</small></button>`;
}
async function doSearch(){
 const raw=$('search-query').value.trim();
 const seq=++searchSequence;
 if(raw.length<2){$('search-results').innerHTML=window.KelwinNav?.commandSuggestions(raw)||'<p class="muted">Nenhuma ação encontrada.</p>';return}
 $('search-results').innerHTML=(window.KelwinNav?.commandSuggestions(raw)||'')+'<p class="muted">Procurando registros…</p>';
 try{
  const data=await api('/api/search?q='+encodeURIComponent(raw));
  if(seq!==searchSequence||!$('search-dialog').open)return;
  $('search-results').innerHTML=(window.KelwinNav?.commandSuggestions(raw)||'')+(data.results.length?'<section class="orbit-command-group" aria-label="Registros"><h3>Registros</h3>'+data.results.map(searchResult).join('')+'</section>':'<p class="muted">Nenhum registro correspondente.</p>');
 }catch(error){if(seq===searchSequence)$('search-results').textContent='Não foi possível pesquisar: '+error.message}
}
function closeSearch(){
 searchSequence++;clearTimeout(searchTimer);
 $('search-dialog').close();searchPreviousFocus?.focus?.();
}
function panel(title,body,other=''){return `<section class="panel"><div class="section-head"><h2>${safe(title)}</h2>${other}</div>${body}</section>`}
function blank(label){return `<p class="blank">${safe(label)}</p>`}
function badge(label,type=''){return `<span class="pill ${type}">${safe(label)}</span>`}
async function showTab(name,focusId=null){
 tab=name;window.KelwinNav?.onPage(name);
 $('pageTitle').textContent=tabs[name];$('content').innerHTML='<p class="muted">Carregando...</p>';
 try{const render={today:todayView,tasks:tasksView,projects:projectsView,contacts:contactsView,opportunities:opportunitiesView,events:eventsView,notes:notesView,automations:automationsView,explore:window.KelwinNav.exploreView};await render[name]();if(focusId&&name==='projects')await showProjectContext(focusId);if(focusId){const target=document.getElementById(`${name}-item-${focusId}`);if(target){target.scrollIntoView({block:'center',behavior:'auto'});target.tabIndex=-1;target.focus()}}}catch(error){$('content').innerHTML=panel('Não foi possível carregar',`<p>${safe(error.message)}</p>`)}
}
// The Mesa is a contextual projection, not another owner of tasks or opportunities.
function workRow(item){
 const isTask=item.kind==='task';
 const where=(isTask?[item.project_name,item.opportunity_title,item.contact_name]:[item.contact_name]).filter(Boolean);
 const context=where.length?`<span class="work-context">${where.map(safe).join(' · ')}</span>`:'';
 const due=item.due_at?dateTime(item.due_at):'Sem data definida';
 const detail=isTask?(item.next_action||''):item.next_action;
 const actions=isTask?`<button type="button" class="mini" data-do="complete" data-id="${safe(item.id)}">Concluir</button><button type="button" class="text-action" data-do="open-task" data-id="${safe(item.id)}">Detalhes</button>`:
 `<button type="button" class="mini" data-do="add-linked-task" data-id="${safe(item.id)}">Criar tarefa</button><button type="button" class="text-action" data-do="contacted" data-id="${safe(item.id)}">Registrar contato</button>`;
 const links=(item.project_id?`<button type="button" class="context-link" data-do="open-project" data-id="${safe(item.project_id)}">Projeto</button>`:'')+
 (isTask&&item.opportunity_id?`<button type="button" class="context-link" data-do="open-opportunity" data-id="${safe(item.opportunity_id)}">Oportunidade</button>`:
 !isTask?`<button type="button" class="context-link" data-do="open-opportunity" data-id="${safe(item.id)}">Abrir oportunidade</button>`:'');
 return `<article class="work-entry" data-kind="${safe(item.kind)}"><div class="work-entry-main"><div class="work-meta"><span>${isTask?'Tarefa':'Retorno'}</span><span aria-hidden="true">·</span><span>${safe(due)}</span>${context}</div><h4>${safe(item.title)}</h4>${detail?`<p class="work-next">${isTask?'Próximo passo':'Fazer agora'}: ${safe(detail)}</p>`:''}<div class="work-links">${links}</div></div><div class="work-entry-actions">${actions}</div></article>`;
}
function workSection(title,description,items,empty){
 return `<section class="work-section" aria-label="${safe(title)}"><header class="work-section-heading"><div><h3>${safe(title)}</h3><p>${safe(description)}</p></div><span class="work-counter" aria-label="${items.length} itens">${items.length}</span></header>${items.length?items.map(workRow).join(''):`<p class="work-empty">${safe(empty)}</p>`}</section>`;
}
async function todayView(){
 const [data,projects]=await Promise.all([api('/api/workspace'),api('/api/projects')]);
 const pending=data.groups;
 const agenda=data.events.length?data.events.map(e=>`<div class="work-compact"><strong>${safe(e.title)}</strong><small>${dateTime(e.start_at)} · ${e.status==='confirmed'?'Confirmado':'Proposto (não confirmado)'}</small></div>`).join(''):blank('Nenhum compromisso local hoje.');
 const alerts=data.alerts.length?data.alerts.map(a=>`<div class="work-compact"><strong>${safe(a.title)}</strong><small>Alerta local · ${dateTime(a.created_at)}</small><button type="button" class="text-action" data-do="dismiss" data-id="${safe(a.id)}">Dispensar alerta</button></div>`).join(''):blank('Nenhum alerta pendente.');
 const opts=projects.filter(p=>p.status==='active').map(p=>`<option value="${safe(p.id)}">${safe(p.name)}</option>`).join('');
 const intro=`<div class="work-hero"><p class="eyebrow">SEU ESPAÇO · ${safe(data.local_date)}</p><h2>Um próximo passo de cada vez.</h2><p>Projetos e oportunidades juntos, organizados pelo que precisa de atenção. Sem criar registros duplicados.</p></div>`;
 const capture=`<form id="quick-task" class="quick-capture" aria-label="Captura rápida de tarefa"><div class="quick-primary"><label for="quick-title">Adicionar uma ação</label><div class="quick-input-row"><input id="quick-title" name="title" type="text" maxlength="200" required placeholder="O que você precisa fazer?" autocomplete="off"><button class="primary" type="submit">Adicionar</button></div></div><div class="quick-details"><label for="quick-project">Projeto <select id="quick-project" name="project_id"><option value="">Sem projeto</option>${opts}</select></label><label for="quick-due">Prazo (opcional) <input id="quick-due" type="datetime-local" name="due_at"></label></div><p id="quick-error" role="alert" class="form-error"></p></form>`;
 $('content').innerHTML=`${intro}${capture}<div class="work-layout"><div class="work-main">${workSection('Precisa de atenção','Vencidas, para hoje ou urgentes',pending.now,'Nenhuma ação urgente.')} ${workSection('Próximos passos','Sem prazo ou nos próximos sete dias',pending.next,'Nenhuma ação na sequência.')} ${pending.blocked.length?workSection('Dependem de algo','Tarefas bloqueadas',pending.blocked,''):''}${pending.later.length?workSection('Mais adiante','Compromissos futuros',pending.later,''):''}</div><aside class="work-aside" aria-label="Contexto do dia"><section><h3>Agenda de hoje</h3>${agenda}<button type="button" class="text-action" data-do="open-events">Ver agenda</button></section><section><h3>Alertas locais</h3>${alerts}</section><p class="work-footnote">Somente informações registradas neste Hub. Calendários externos não estão conectados.</p></aside></div>`;
}
async function quickCapture(form){
 const title=form.querySelector('[name="title"]').value.trim();
 const error=$('quick-error');
 if(!title){error.textContent='Informe o que você precisa fazer.';return}
 const button=form.querySelector('[type="submit"]');
 button.disabled=true;error.textContent='';
 try{
  await api('/api/tasks','POST',{title,project_id:form.querySelector('[name="project_id"]').value||null,due_at:form.querySelector('[name="due_at"]').value||null});
  notify('Ação adicionada');await showTab('today');$('quick-title')?.focus();
 }catch(err){error.textContent=err.message;button.disabled=false}
}
async function projectsView(){const data=await api('/api/projects');$('content').innerHTML=`<div class="section-head"><p class="muted">Separe seus projetos por área, sem duplicar issues do GitHub.</p><button class="primary" data-do="add-project">+ Novo projeto</button></div>${panel('Meus projetos',data.length?`<div class="list">${data.map(x=>`<div id="projects-item-${safe(x.id)}" class="item"><div class="item-info"><strong>${safe(x.name)}</strong><small>${safe(x.area)} · criado ${dateTime(x.created_at)}</small></div>${badge(x.status)}<button class="mini" data-do="project-context" data-id="${safe(x.id)}" aria-expanded="false" aria-controls="project-context-${safe(x.id)}">Contexto</button><button class="mini" data-do="edit-project" data-id="${safe(x.id)}">Editar</button></div><div class="project-context" id="project-context-${safe(x.id)}" hidden></div>`).join('')}</div>`:blank('Nenhum projeto cadastrado.'))}`}
async function showProjectContext(id){
 const region=document.getElementById(`project-context-${id}`);
 if(!region)return;
 const trigger=document.querySelector(`[data-do="project-context"][data-id="${id}"]`);
 if(!region.hidden){region.hidden=true;trigger?.setAttribute('aria-expanded','false');return}
 region.hidden=false;trigger?.setAttribute('aria-expanded','true');
 region.textContent='Carregando contexto…';
 try{
  const data=await api('/api/projects/'+encodeURIComponent(id)+'/context');
  const [linkedNotes,activity,allEvents]=await Promise.all([api('/api/notes?project_id='+encodeURIComponent(id)),api('/api/activity?kind=project&ident='+encodeURIComponent(id)),api('/api/events')]);
  const relatedEvents=allEvents.filter(e=>e.project_id===id&&e.status!=='cancelled').slice(0,5);
  const c=data.counts;
  const overview=`${c.open} em andamento · ${c.blocked} bloqueadas · ${c.done} concluídas`;
  const taskRows=data.tasks.map(t=>`<article class="project-task"><div><strong>${safe(t.title)}</strong><small>${safe(t.status)}${t.due_at?' · '+dateTime(t.due_at):''}${t.opportunity_title?' · '+safe(t.opportunity_title):''}</small></div>${t.status!=='done'?`<button type="button" class="mini" data-do="complete" data-id="${safe(t.id)}">Concluir</button>`:''}</article>`).join('');
  region.innerHTML=`<div class="project-context-head"><div><h3>Dentro deste projeto</h3><p>${safe(overview)}</p>${data.next_task?`<p>Próxima tarefa: <strong>${safe(data.next_task.title)}</strong></p>`:''}</div><button type="button" class="primary" data-do="add-project-task" data-id="${safe(id)}">+ Tarefa neste projeto</button></div><div class="project-task-list">${taskRows||'<p class="muted">Nenhuma tarefa vinculada ainda.</p>'}</div><div class="context-extra"><h4>Notas <button class="mini" type="button" data-do="add-project-note" data-id="${safe(id)}">+ Nota</button></h4>${linkedNotes.slice(0,8).map(n=>`<p><strong>${safe(n.title)}</strong> — ${safe(n.body.slice(0,140))}</p>`).join('')||'<p class="muted">Sem notas ainda.</p>'}<h4>Compromissos</h4>${relatedEvents.map(e=>`<p>${safe(e.title)} · ${dateTime(e.start_at)} · ${safe(e.status)}</p>`).join('')||'<p class="muted">Sem compromissos vinculados.</p>'}<h4>Atividades registradas</h4>${activity.slice(0,8).map(a=>`<p><span class="muted">${dateTime(a.at)}</span> · ${safe(a.kind)} · ${safe(a.action)}</p>`).join('')||'<p class="muted">Sem ações registradas.</p>'}</div>`;
 }catch(error){region.textContent='Falha ao consultar projeto: '+error.message}
}
async function contactsView(){const data=await api('/api/contacts');$('content').innerHTML=`<div class="section-head"><p class="muted">Pessoas com quem você se relaciona profissionalmente.</p><button class="primary" data-do="add-contact">+ Novo contato</button></div>${panel('Lista de contatos',data.length?`<div class="list">${data.map(x=>`<div id="contacts-item-${safe(x.id)}" class="item"><div class="item-info"><strong>${safe(x.name)}</strong><small>${safe(x.company||'Sem empresa')} · ${safe(x.email||'Sem e-mail')}</small></div>${badge(x.category)}<button class="mini" data-do="edit-contact" data-id="${safe(x.id)}">Editar</button></div>`).join('')}</div>`:blank('Comece cadastrando um contato fictício para testar.'))}`}
function opportunityRow(x){
 const when=x.followup_at?'Retorno: '+dateTime(x.followup_at):'Sem prazo de retorno';
 return `<article id="opportunities-item-${safe(x.id)}" class="opportunity-entry"><div class="opportunity-content"><div class="work-meta"><span>${safe(x.contact_name)}</span><span>·</span><span>${safe(x.kind)}</span><span>·</span>${badge(x.status)}</div><h3>${safe(x.title)}</h3><p>Próxima ação: ${safe(x.next_action)}</p><small>${when}</small></div><div class="row-actions"><button class="mini" data-do="edit-opportunity" data-id="${safe(x.id)}">Editar</button>${!['won','lost','archived'].includes(x.status)?`<button class="mini" data-do="add-linked-task" data-id="${safe(x.id)}">Criar tarefa</button><button class="mini" data-do="contacted" data-id="${safe(x.id)}">Registrar contato</button>`:''}</div></article>`;
}
function renderOpportunityBoard(board){
 const kind=$('opp-filter-kind').value,status=$('opp-filter-status').value,term=$('opp-filter-text').value.trim().toLocaleLowerCase('pt-BR');
 const labels={overdue:['Retornos vencidos','Ações com prazo ultrapassado.'],upcoming:['Próximos sete dias','Retornos agendados para breve.'],later:['Mais adiante','Acompanhamentos com prazo futuro.'],awaiting:['Aguardando','Sem prazo registrado.'],undated:['Sem prazo definido','Oportunidades ativas sem retorno marcado.'],closed:['Encerradas e arquivadas','Mantidas para consulta de histórico.']};
 let shown=0;
 const html=Object.entries(labels).map(([group,[title,description]])=>{
  const items=board.groups[group].filter(x=>(!kind||x.kind===kind)&&(!status||x.status===status)&&(!term||[x.title,x.contact_name,x.next_action].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(term))));
  if(!items.length)return '';
  shown+=items.length;
  return `<section class="opportunity-group"><div class="work-section-heading"><div><h2>${safe(title)}</h2><p>${safe(description)}</p></div><span class="work-counter">${items.length}</span></div>${items.map(opportunityRow).join('')}</section>`;
 }).join('');
 $('opp-board').innerHTML=html||'<p class="work-empty">Nenhuma oportunidade corresponde aos filtros.</p>';
 $('opp-count').textContent=shown+' resultado(s)';
}
async function opportunitiesView(){
 const board=await api('/api/opportunities/board');
 $('content').innerHTML=`<div class="section-head"><p class="muted">Retornos por prazo e situação, com próximos passos explícitos.</p><button class="primary" data-do="add-opportunity">+ Nova oportunidade</button></div><div class="opportunity-filters"><label for="opp-filter-kind">Categoria<select id="opp-filter-kind"><option value="">Todas</option><option value="service">Serviços</option><option value="job">Candidaturas</option><option value="music">Música</option><option value="other">Outras</option></select></label><label for="opp-filter-status">Situação<select id="opp-filter-status"><option value="">Todas</option><option value="new">Nova</option><option value="active">Ativa</option><option value="waiting">Aguardando</option><option value="won">Ganha</option><option value="lost">Perdida</option><option value="archived">Arquivada</option></select></label><label for="opp-filter-text">Filtrar nome ou ação<input id="opp-filter-text" type="search" autocomplete="off" placeholder="Contato, ação ou oportunidade…"></label></div><p id="opp-count" class="muted" aria-live="polite"></p><div id="opp-board" class="opportunity-board"></div>`;
 const filter=()=>renderOpportunityBoard(board);
 for(const id of ['opp-filter-kind','opp-filter-status','opp-filter-text'])$(id).addEventListener('input',filter);
 filter();
}

async function tasksView(){const data=await api('/api/tasks');$('content').innerHTML=`<div class="section-head"><p class="muted">Tarefas próprias do Hub, com histórico de conclusão.</p><button class="primary" data-do="add-task">+ Nova tarefa</button></div>${panel('Todas as tarefas',data.length?`<div class="list">${data.map(x=>`<div id="tasks-item-${safe(x.id)}" class="item"><div class="item-info"><strong>${safe(x.title)}</strong><small>${x.due_at?dateTime(x.due_at):'Sem prazo'} · prioridade ${x.priority}</small></div><div class="row-actions">${badge(x.status)}<button class="mini" data-do="edit-task" data-id="${safe(x.id)}">Editar</button>${x.status!=='done'?`<button class="mini" data-do="complete" data-id="${safe(x.id)}">Concluir</button>`:''}</div></div>`).join('')}</div>`:blank('Nenhuma tarefa cadastrada.'))}`}
async function notesView(){
 const notes=await api('/api/notes');
 $('content').innerHTML=`<div class="section-head"><p class="muted">Informações que merecem contexto, mas ainda não são tarefas.</p><button type="button" class="primary" data-do="add-note">+ Nova nota</button></div>${panel('Notas do Hub',notes.length?`<div class="list">${notes.map(n=>`<article id="notes-item-${safe(n.id)}" class="item"><div class="item-info"><strong>${safe(n.title)}</strong><small>${safe(n.body.slice(0,180))}</small><small>Atualizada ${dateTime(n.updated_at)}</small></div><button type="button" class="mini" data-do="edit-note" data-id="${safe(n.id)}">Editar</button></article>`).join('')}</div>`:blank('Ainda não há notas. Registre uma ideia para começar.'))}`;
}
let eventWindow='week';
async function eventsView(){
 const data=await api('/api/events');
 const today=new Date();today.setHours(0,0,0,0);
 const weekEnd=new Date(today);weekEnd.setDate(weekEnd.getDate()+7);
 const selected=data.filter(x=>eventWindow==='all'||(new Date(x.start_at)>=today&&(eventWindow==='today'?new Date(x.start_at).toDateString()===today.toDateString():new Date(x.start_at)<weekEnd)));
 const labels={today:'Hoje',week:'Próximos 7 dias',all:'Todos'};
 const switcher=`<div class="calendar-views" aria-label="Período da agenda">${Object.entries(labels).map(([key,label])=>`<button type="button" data-do="event-window" data-value="${key}" class="mini" aria-pressed="${key===eventWindow}">${label}</button>`).join('')}</div>`;
 const content=selected.map(x=>`<article id="events-item-${safe(x.id)}" class="item"><div class="item-info"><strong>${safe(x.title)}</strong><small>${dateTime(x.start_at)} até ${dateTime(x.end_at)}</small><small>${x.project_id?'Vinculado a projeto · ':''}${x.contact_id?'Vinculado a contato':''}</small></div><div class="row-actions">${badge(x.status,x.status==='confirmed'?'good':'warn')}<button class="mini" data-do="edit-event" data-id="${safe(x.id)}">Editar</button><button type="button" class="mini" data-do="event-transcripts" data-id="${safe(x.id)}" aria-expanded="false">Transcrições</button></div></article><section class="transcript-context" id="event-transcripts-${safe(x.id)}" hidden></section>`).join('');
 $('content').innerHTML=`<div class="section-head"><p class="muted">Eventos locais; horários confirmados não podem se sobrepor.</p><button class="primary" data-do="add-event">+ Novo evento</button><button type="button" class="mini" data-do="availability-open">Horários livres</button></div>${switcher}${panel('Agenda local',selected.length?`<div class="list">${content}</div>`:blank('Nenhum compromisso neste período.'))}`;
}
async function automationsView(){const data=await api('/api/automations'),runs=await api('/api/automation-runs'),health=await api('/api/automation-health');
 const cards=data.map(x=>{const enabled=x.status==='available';const c=x.settings||{};return `<section class="panel automation-card ${enabled?'':'disabled'}"><header>${badge(x.atlas)} ${badge(enabled?'Disponível':'Planejada',enabled?'good':'')}</header><h2>${safe(x.name)}</h2><p>${safe(x.description)}</p><small class="muted">Motor: ${safe(x.engine)} · risco: ${safe(x.risk)}</small>${enabled?`<footer><label><input id="autoEnabled" type="checkbox" ${c.enabled?'checked':''}> Ativa</label><label for="autoDays">Dias <input id="autoDays" type="number" min="1" max="365" value="${c.threshold_days}"></label></footer><footer><button class="mini" data-do="save-auto">Salvar</button><button class="primary" data-do="run-auto">Executar agora</button></footer><small class="muted">Última execução: ${c.last_run_at?dateTime(c.last_run_at):'nunca'}</small>`:''}</section>`}).join('');
 const history=runs.length?`<div class="list">${runs.slice(0,10).map(x=>`<div class="item"><div class="item-info"><strong>${safe(x.code)}</strong><small>${dateTime(x.executed_at)} · ${x.scanned} analisadas, ${x.created} alertas novos</small></div>${badge(x.status)}</div>`).join('')}</div>`:blank('Ainda não existem execuções.');
 $('content').innerHTML=`<p class="intro">Escolha, configure e teste automações. O n8n permanece opcional e pode ser habilitado depois.</p>${panel('Estado do agendador',`<p>${health.scheduler_enabled?'Agendador local habilitado':'Agendador local desativado'} · última checagem: ${health.last_check_at?dateTime(health.last_check_at):'ainda não realizada'}</p>${health.last_failure_type?`<p role="alert">Falha detectada: ${safe(health.last_failure_type)} · ${dateTime(health.last_failure_at)}</p>`:''}`)}<div class="cards">${cards}</div>${panel('Histórico de execução',history)}<div class="note">O n8n pode ser iniciado separadamente por Docker. O arquivo de workflow opcional está no pacote do projeto. Nenhuma automação deste piloto envia mensagens a terceiros.</div>`;
}
function openDialog(title,fields,submit,onSuccess=null){
 $('dialog-body').innerHTML=`<h2>${safe(title)}</h2>${fields.map(f=>`<div class="field"><label for="f_${safe(f.key)}">${safe(f.label)}</label>${f.type==='textarea'?`<textarea id="f_${safe(f.key)}" name="${safe(f.key)}" rows="5" maxlength="12000" ${f.required?'required':''}>${safe(f.value||'')}</textarea>`:f.type==='select'?`<select id="f_${safe(f.key)}" name="${safe(f.key)}" ${f.required?'required':''}>${f.options.map(o=>`<option value="${safe(o.value)}" ${f.value===o.value?'selected':''}>${safe(o.label)}</option>`).join('')}</select>`:`<input id="f_${safe(f.key)}" name="${safe(f.key)}" type="${safe(f.type||'text')}" ${f.required?'required':''} ${f.value?`value="${safe(f.value)}"`:''} ${f.min?`min="${safe(f.min)}"`:''} ${f.max?`max="${safe(f.max)}"`:''} ${f.accept?`accept="${safe(f.accept)}"`:''}>`}</div>`).join('')}`;
 $('dialog-error').textContent='';$('dialog').showModal();
 $('dynamic-form').onsubmit=async(e)=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.target).entries());
  const invalid=fields.find(f=>f.required&&typeof values[f.key]==='string'&&!values[f.key].trim());
  if(invalid){$('dialog-error').textContent=`${invalid.label}: campo obrigatório não pode ficar vazio`;$(`f_${invalid.key}`)?.focus();return}
  try{await submit(values);$('dialog').close();notify('Registro salvo');if(onSuccess){await onSuccess()}else{await showTab(tab)}}catch(error){$('dialog-error').textContent=error.message}};
}
const field=(key,label,type='text',required=true)=>({key,label,type,required});
async function addContact(){openDialog('Novo contato',[field('name','Nome'),field('company','Empresa','text',false),field('email','E-mail','email',false),field('phone','Telefone','text',false)],(x)=>api('/api/contacts','POST',x))}
async function addProject(){openDialog('Novo projeto',[field('name','Nome'),field('area','Área (pessoal, estudos, trabalho...)')],(x)=>api('/api/projects','POST',x))}
async function addOpportunity(){const contacts=await api('/api/contacts');if(!contacts.length){notify('Cadastre um contato primeiro');await showTab('contacts');return}
 openDialog('Nova oportunidade',[{key:'contact_id',label:'Contato',type:'select',required:true,options:contacts.map(x=>({value:x.id,label:x.name}))},field('title','Descrição'),{key:'kind',label:'Categoria',type:'select',required:true,options:[{value:'service',label:'Serviço/cliente'},{value:'job',label:'Candidatura'},{value:'music',label:'Música'},{value:'other',label:'Outra'}]},field('next_action','Próxima ação'),field('followup_at','Prazo para retorno','datetime-local',false),field('value_brl','Valor estimado (R$)','number',false)],(x)=>api('/api/opportunities','POST',{...x,followup_at:x.followup_at||null,value_brl:x.value_brl||null}))}
async function addTask(opportunityId,projectId=null){const projects=await api('/api/projects');const linked=opportunityId?(await api('/api/opportunities')).find(x=>x.id===opportunityId):null;const opts=[{value:'',label:'Sem projeto'},...projects.map(x=>({value:x.id,label:x.name}))];openDialog('Nova tarefa',[{...field('title','O que fazer?'),value:linked?.next_action||''},{key:'project_id',label:'Projeto',type:'select',required:false,value:projectId||'',options:opts},{...field('due_at','Prazo','datetime-local',false),value:linked?.followup_at?localInputValue(linked.followup_at):''},{key:'priority',label:'Prioridade',type:'select',required:true,options:[{value:'1',label:'Normal'},{value:'2',label:'Alta'},{value:'3',label:'Urgente'},{value:'0',label:'Baixa'}]}],(x)=>api('/api/tasks','POST',{...x,priority:Number(x.priority),project_id:x.project_id||null,opportunity_id:opportunityId||null,due_at:x.due_at||null}))}
async function addNote(projectId=null){
 const [projects,contacts,opportunities]=await Promise.all([api('/api/projects'),api('/api/contacts'),api('/api/opportunities')]);
 const options=(rows,label)=>[{value:'',label},...rows.map(item=>({value:item.id,label:item.name||item.title}))];
 openDialog('Nova nota',[field('title','Título'),{key:'body',label:'Conteúdo',type:'textarea',required:true},
 {key:'project_id',label:'Projeto',type:'select',value:projectId||'',required:false,options:options(projects,'Sem projeto')},
 {key:'contact_id',label:'Contato',type:'select',required:false,options:options(contacts,'Sem contato')},
 {key:'opportunity_id',label:'Oportunidade',type:'select',required:false,options:options(opportunities,'Sem oportunidade')}],
 x=>api('/api/notes','POST',{...x,project_id:x.project_id||null,contact_id:x.contact_id||null,opportunity_id:x.opportunity_id||null}),
 projectId?()=>showTab('projects',projectId):null);
}
async function editNote(id){
 const note=(await api('/api/notes')).find(x=>x.id===id);if(!note)throw Error('Nota não encontrada');
 openDialog('Editar nota',[{...field('title','Título'),value:note.title},
 {key:'body',label:'Conteúdo',type:'textarea',required:true,value:note.body}],x=>api(`/api/notes/${id}`,'PATCH',x));
}
async function showEventTranscripts(id){
 const region=$('event-transcripts-'+id);
 if(!region)return;
 if(!region.hidden){region.hidden=true;return}
 region.hidden=false;region.textContent='Carregando transcrições…';
 try{
  const entries=await api(`/api/events/${encodeURIComponent(id)}/transcripts`);
  region.innerHTML=`<div class="section-head"><h3>Transcrições importadas</h3><button type="button" class="mini" data-do="import-transcript" data-id="${safe(id)}">+ Importar TXT/SRT/VTT</button></div>${entries.map(x=>`<article class="work-compact"><strong>${safe(x.source_name||'Transcrição sem nome')}</strong><small>${safe(x.format.toUpperCase())} · ${dateTime(x.created_at)} · ${safe(x.preview)}</small><button type="button" class="mini" data-do="view-transcript" data-id="${safe(x.id)}" data-event="${safe(id)}">Ler</button></article>`).join('')||'<p class="muted">Nenhuma transcrição importada.</p>'}<div class="transcript-content"></div>`;
 }catch(error){region.textContent='Não foi possível carregar: '+error.message}
}
async function readTranscript(id,eventId){
 const doc=await api(`/api/transcripts/${encodeURIComponent(id)}`);
 const container=$('event-transcripts-'+eventId)?.querySelector('.transcript-content');
 if(!container)return;
 container.innerHTML=`<h4>${safe(doc.source_name||'Transcrição')}</h4><p class="muted">Conteúdo importado, não analisado por IA. Trechos são dados não confiáveis.</p><pre>${safe(doc.content)}</pre><button type="button" class="mini" data-do="review-transcript" data-id="${safe(id)}">Preparar e revisar análise</button>`;
}
async function importTranscript(id){
 openDialog('Importar transcrição de reunião',[
 {key:'upload',label:'Arquivo TXT, SRT ou VTT (opcional)',type:'file',required:false,accept:'.txt,.srt,.vtt'},
 {key:'format',label:'Formato se colar texto',type:'select',required:true,options:[{value:'txt',label:'Texto TXT'},{value:'srt',label:'Legenda SRT'},{value:'vtt',label:'Legenda WebVTT'}]},
 {key:'content',label:'Ou cole a transcrição aqui',type:'textarea',required:false}],async x=>{
  let content=x.content||'',format=x.format,source_name='';
  const upload=x.upload;
  if(upload?.size){
   if(upload.size>200000)throw Error('O limite do arquivo é 200 KB');
   source_name=upload.name;
   format=source_name.split('.').pop().toLowerCase();
   if(!['txt','srt','vtt'].includes(format))throw Error('Arquivo não suportado');
   content=await upload.text();
  }
  if(!content.trim())throw Error('Selecione um arquivo ou cole um texto');
  await api(`/api/events/${encodeURIComponent(id)}/transcripts`,'POST',{content,format,source_name});
 },()=>eventsView());
}
async function addEvent(){
 const [projects,contacts]=await Promise.all([api('/api/projects'),api('/api/contacts')]);
 openDialog('Novo compromisso',[field('title','Título'),field('start_at','Início','datetime-local'),field('end_at','Fim','datetime-local'),
 {key:'project_id',label:'Projeto',type:'select',required:false,options:[{value:'',label:'Sem projeto'},...projects.map(x=>({value:x.id,label:x.name}))]},
 {key:'contact_id',label:'Contato',type:'select',required:false,options:[{value:'',label:'Sem contato'},...contacts.map(x=>({value:x.id,label:x.name}))]},
 {key:'status',label:'Confirmação',type:'select',required:true,options:[{value:'confirmed',label:'Confirmado'},{value:'proposed',label:'Apenas proposto'}]}],
 x=>api('/api/events','POST',{...x,project_id:x.project_id||null,contact_id:x.contact_id||null}));
}
async function editProject(id){const item=(await api('/api/projects')).find(x=>x.id===id);if(!item)throw Error('Projeto não encontrado');
 openDialog('Editar projeto',[{...field('name','Nome'),value:item.name},{...field('area','Área'),value:item.area},{key:'status',label:'Estado',type:'select',value:item.status,required:true,options:[{value:'active',label:'Ativo'},{value:'paused',label:'Pausado'},{value:'completed',label:'Concluído'},{value:'archived',label:'Arquivado'}]}],x=>api(`/api/projects/${id}`,'PATCH',x))}
async function editContact(id){const item=(await api('/api/contacts')).find(x=>x.id===id);if(!item)throw Error('Contato não encontrado');
 openDialog('Editar contato',[{...field('name','Nome'),value:item.name},{...field('company','Empresa','text',false),value:item.company},{...field('email','E-mail','email',false),value:item.email},{...field('phone','Telefone','text',false),value:item.phone}],x=>api(`/api/contacts/${id}`,'PATCH',x))}
async function editOpportunity(id){const item=(await api('/api/opportunities')).find(x=>x.id===id);if(!item)throw Error('Oportunidade não encontrada');
 openDialog('Editar oportunidade',[{...field('title','Título'),value:item.title},{...field('next_action','Próxima ação'),value:item.next_action},{key:'status',label:'Situação',type:'select',required:true,value:item.status,options:[{value:'new',label:'Nova'},{value:'active',label:'Ativa'},{value:'waiting',label:'Aguardando'},{value:'won',label:'Concluída/ganha'},{value:'lost',label:'Perdida'},{value:'archived',label:'Arquivada'}]},{...field('followup_at','Próximo retorno','datetime-local',false),value:item.followup_at?localInputValue(item.followup_at):''}],x=>api(`/api/opportunities/${id}`,'PATCH',{...x,followup_at:x.followup_at||null}))}
async function editTask(id){const item=(await api('/api/tasks')).find(x=>x.id===id);if(!item)throw Error('Tarefa não encontrada');
 openDialog('Editar tarefa',[{...field('title','Título'),value:item.title},{...field('due_at','Prazo','datetime-local',false),value:item.due_at?localInputValue(item.due_at):''},{key:'status',label:'Estado',type:'select',required:true,value:item.status,options:[{value:'open',label:'Aberta'},{value:'blocked',label:'Bloqueada'},{value:'done',label:'Concluída'}]}],x=>api(`/api/tasks/${id}`,'PATCH',{...x,due_at:x.due_at||null}))}
async function editEvent(id){const item=(await api('/api/events')).find(x=>x.id===id);if(!item)throw Error('Evento não encontrado');
 openDialog('Editar compromisso',[{...field('title','Título'),value:item.title},
 {...field('start_at','Início','datetime-local'),value:localInputValue(item.start_at)},
 {...field('end_at','Fim','datetime-local'),value:localInputValue(item.end_at)},
 {key:'status',label:'Situação',type:'select',required:true,value:item.status,options:[{value:'confirmed',label:'Confirmado'},{value:'proposed',label:'Apenas proposto'},{value:'cancelled',label:'Cancelado'}]}],
 x=>api(`/api/events/${id}`,'PATCH',x))}

async function handleAction(button){const a=button.dataset.do,id=button.dataset.id;const parentRegion=button.closest('.project-context');const activeProject=parentRegion?.id.replace('project-context-','');
 try{switch(a){case'add-contact':await addContact();return;case'add-note':await addNote();return;case'add-project-note':await addNote(id);return;case'edit-note':await editNote(id);return;case'add-project':await addProject();return;case'add-opportunity':await addOpportunity();return;case'add-task':await addTask(null);return;case'add-linked-task':await addTask(id);return;case'add-project-task':await addTask(null,id);return;case'project-context':await showProjectContext(id);return;case'add-event':await addEvent();return;case'availability-open':await window.KelwinAvailability.open();return;case'event-transcripts':await showEventTranscripts(id);return;case'import-transcript':await importTranscript(id);return;case'view-transcript':await readTranscript(id,button.dataset.event);return;case'review-transcript':await window.KelwinReview.open(id);return;case'event-window':eventWindow=button.dataset.value;await eventsView();document.querySelector(`[data-do="event-window"][data-value="${eventWindow}"]`)?.focus();return;case'edit-project':await editProject(id);return;case'edit-contact':await editContact(id);return;case'edit-opportunity':await editOpportunity(id);return;case'edit-task':await editTask(id);return;case'edit-event':await editEvent(id);return;
 case'open-task':await showTab('tasks',id);return;case'open-project':await showTab('projects',id);return;case'open-opportunity':await showTab('opportunities',id);return;case'open-events':await showTab('events');return;
 case'complete':await api(`/api/tasks/${id}`,'PATCH',{status:'done'});break;
 case'contacted':await api(`/api/opportunities/${id}/contact`,'POST',{});break;
 case'dismiss':await api(`/api/alerts/${id}/dismiss`,'POST',{});break;
 case'save-auto':await api('/api/automations/stale_opportunities','PATCH',{enabled:$('autoEnabled').checked,threshold_days:Number($('autoDays').value)});break;
 case'run-auto':{const run=await api('/api/automations/stale_opportunities/run','POST',{});notify(run.executed?`${run.created} novo(s) alerta(s)`:'Automação desativada');await showTab('automations');return}
 default:return}notify('Atualizado');await showTab(tab,activeProject&&tab==='projects'?activeProject:null)}catch(error){notify(`Erro: ${error.message}`)}
}
window.addEventListener('DOMContentLoaded',async()=>{
 document.documentElement.dataset.theme=(()=>{try{return localStorage.getItem('kh_theme')||(window.matchMedia?.('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(_){return 'light'}})();$('theme').addEventListener('click',changeTheme);$('export').addEventListener('click',async()=>{try{const data=await api('/api/export');const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='kelwin-hub-export.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Exportação pronta — proteja o arquivo privado')}catch(error){notify(error.message)}});
 $('login-form').addEventListener('submit',async(e)=>{e.preventDefault();$('login-error').textContent='';try{await api('/api/login','POST',{password:$('password').value});await showApp()}catch(error){$('login-error').textContent=error.message}});
 $('search-open').addEventListener('click',openSearch);
 $('search-close').addEventListener('click',closeSearch);
 $('search-dialog').addEventListener('close',()=>{searchSequence++;clearTimeout(searchTimer);searchPreviousFocus?.focus?.()});
 $('search-query').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(doSearch,170)});
 $('search-results').addEventListener('click',async e=>{
  const b=e.target.closest('button[data-tab]');if(!b)return;
  const tabName=b.dataset.tab,id=b.dataset.id;
  if(!Object.prototype.hasOwnProperty.call(tabs,tabName))return;
  closeSearch();await showTab(tabName,id);
 });
 $('nav').addEventListener('click',(e)=>{const b=e.target.closest('[data-tab]');if(b)showTab(b.dataset.tab)});
 $('content').addEventListener('click',(e)=>{const b=e.target.closest('button[data-tab],button[data-do]');if(!b)return;if(b.dataset.tab)showTab(b.dataset.tab);else handleAction(b)});
 $('content').addEventListener('submit',(e)=>{if(e.target.id==='quick-task'){e.preventDefault();quickCapture(e.target)}});
 document.addEventListener('keydown',(e)=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'&&!$('shell').hidden){e.preventDefault();openSearch();return}const tag=document.activeElement?.tagName;const busy=['INPUT','TEXTAREA','SELECT'].includes(tag)||$('dialog').open||$('search-dialog').open;if(e.key.toLowerCase()==='q'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!busy&&!$('shell').hidden){e.preventDefault();showTab('today').then(()=>$('quick-title')?.focus())}});
 $('logout').addEventListener('click',async()=>{try{await api('/api/logout','POST',{})}finally{showAuth()}});
 $('cancel-dialog').addEventListener('click',()=>$('dialog').close());
 await showApp();
});
