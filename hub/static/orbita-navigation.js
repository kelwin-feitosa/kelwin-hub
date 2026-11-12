'use strict';
/* The ORBITA navigation is declarative: new capabilities join the directory,
 * not the permanent navigation. No user content is put into localStorage. */
window.KelwinNav = (() => {
  const directory = Object.freeze([
    {tab:'today', label:'Mesa', group:'Começar', icon:'◈', detail:'Suas próximas ações e o que merece atenção.'},
    {tab:'tasks', label:'Tarefas', group:'Trabalhar', icon:'☑', detail:'Criar, acompanhar e concluir ações.'},
    {tab:'projects', label:'Projetos', group:'Trabalhar', icon:'▤', detail:'Retomar o trabalho e recuperar contexto.'},
    {tab:'notes', label:'Notas', group:'Trabalhar', icon:'✎', detail:'Registrar conhecimento e observações.'},
    {tab:'opportunities', label:'Oportunidades', group:'Acompanhar', icon:'◇', detail:'Candidaturas, negociações e próximos passos.'},
    {tab:'contacts', label:'Contatos', group:'Acompanhar', icon:'♙', detail:'Pessoas e organizações relacionadas.'},
    {tab:'events', label:'Agenda', group:'Planejar', icon:'▦', detail:'Compromissos, reuniões e horários livres.'},
    {tab:'automations', label:'Automações', group:'Planejar', icon:'↗', detail:'Alertas e regras locais.'},
  ]);
  const actions = Object.freeze([
    {action:'add-task', label:'Criar tarefa', detail:'Registrar uma próxima ação.'},
    {action:'add-note', label:'Criar nota', detail:'Anotar algo sem perder o contexto.'},
    {action:'add-project', label:'Criar projeto', detail:'Iniciar um novo espaço de trabalho.'},
    {action:'add-event', label:'Criar compromisso', detail:'Reservar um horário na agenda.'},
    {action:'add-contact', label:'Criar contato', detail:'Registrar uma pessoa ou organização.'},
    {action:'add-opportunity', label:'Criar oportunidade', detail:'Acompanhar uma proposta ou candidatura.'},
  ]);
  const normalize = text => String(text || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  let recent = [];
  let navigatingBack = false;

  function commandCard(item) {
    const attribute = item.tab ? `data-tab="${item.tab}"` : `data-do="${item.action}"`;
    const icon = item.icon || '+';
    return `<button type="button" class="orbit-command" ${attribute}>` +
      `<span class="orbit-command-icon" aria-hidden="true">${icon}</span>` +
      `<span><strong>${item.label}</strong><small>${item.detail}</small></span></button>`;
  }
  function group(title, entries) {
    if (!entries.length) return '';
    return `<section class="orbit-command-group" aria-label="${title}"><h3>${title}</h3>` +
      `<div class="orbit-command-list">${entries.map(commandCard).join('')}</div></section>`;
  }
  function commandSuggestions(value) {
    const q = normalize(value);
    const matches = entry => !q || normalize(`${entry.label} ${entry.detail} ${entry.group || ''}`).includes(q);
    const recentEntries = q ? [] : recent.slice(0, 3)
      .map(name => directory.find(item => item.tab === name)).filter(Boolean);
    return group('Recentes', recentEntries) +
      group('Ações rápidas', actions.filter(matches)) +
      group('Áreas do Hub', directory.filter(matches));
  }
  function exploreView() {
    const sections = ['Começar', 'Trabalhar', 'Acompanhar', 'Planejar'].map(name => {
      const entries = directory.filter(item => item.group === name);
      return `<section class="orbit-explore-group" aria-label="${name}"><h3>${name}</h3>` +
        `<div class="orbit-explore-list">${entries.map(item =>
          `<button type="button" class="orbit-explore-entry" data-tab="${item.tab}">` +
            `<span class="orbit-glyph" aria-hidden="true">${item.icon}</span>` +
            `<span><strong>${item.label}</strong><small>${item.detail}</small></span>` +
            `<span class="orbit-chevron" aria-hidden="true">›</span></button>`
        ).join('')}</div></section>`;
    }).join('');
    document.getElementById('content').innerHTML =
      `<div class="orbit-intro"><p class="eyebrow">ENCONTRE SEU CAMINHO</p>` +
      `<h2>Tudo o que precisa, no momento certo.</h2>` +
      `<p>As ferramentas estão organizadas por finalidade, sem uma lista interminável na lateral. ` +
      `As ações mais úteis também aparecem dentro dos projetos e reuniões.</p>` +
      `<button type="button" class="primary" data-orbita="launch">Buscar ou executar ação</button></div>` +
      `<div class="orbit-explore-groups">${sections}</div>` +
      `<section class="orbit-utilities" aria-label="Privacidade e utilitários">` +
      `<h3>Seu Hub</h3><p>Seus dados são locais. Arquivos exportados devem ser protegidos.</p>` +
      `<div class="orbit-utility-actions"><button type="button" class="ghost" data-orbita="export">Exportar dados</button>` +
      `<button type="button" class="ghost" data-orbita="logout">Sair da sessão</button></div></section>`;
  }
  function onPage(name) {
    const primary = ['today','projects','events'].includes(name) ? name : 'explore';
    document.querySelectorAll('#nav [data-tab]').forEach(button => {
      const current = button.dataset.tab === primary;
      button.classList.toggle('active', current);
      if (current) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    if (name !== 'explore') recent = [name, ...recent.filter(value => value !== name)].slice(0, 5);
    // Browser history contains only a public module identifier, never record IDs.
    if (!navigatingBack && window.location.hash !== '#' + name)
      window.history.pushState({tab:name}, '', '#' + name);
  }
  function showSuggestions() {
    const q = document.getElementById('search-query');
    document.getElementById('search-results').innerHTML = commandSuggestions(q.value);
  }
  function init() {
    const search = document.getElementById('search-query');
    const results = document.getElementById('search-results');
    document.getElementById('create-open').addEventListener('click', () => {
      window.openSearch();
      search.value = 'criar';
      window.doSearch();
    });
    // The existing result handler handles records and destinations; extend it
    // only for registered, local creation commands.
    results.addEventListener('click', event => {
      const button = event.target.closest('button[data-do]');
      if (!button || !actions.some(item => item.action === button.dataset.do)) return;
      window.closeSearch();
      window.handleAction(button);
    });
    search.addEventListener('keydown', event => {
      if (!['ArrowDown', 'Enter'].includes(event.key)) return;
      const first = results.querySelector('button[data-tab], button[data-do]');
      if (!first) return;
      event.preventDefault();
      if (event.key === 'Enter') first.click(); else first.focus();
    });
    results.addEventListener('keydown', event => {
      if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
      const buttons = [...results.querySelectorAll('button[data-tab], button[data-do]')];
      const index = buttons.indexOf(document.activeElement);
      if (index < 0) return;
      event.preventDefault();
      if (event.key === 'ArrowDown') buttons[Math.min(index + 1, buttons.length - 1)].focus();
      else if (index === 0) search.focus();
      else buttons[index - 1].focus();
    });
    document.getElementById('content').addEventListener('click', event => {
      const button = event.target.closest('button[data-orbita]');
      if (!button) return;
      const task = button.dataset.orbita;
      if (task === 'launch') window.openSearch();
      if (task === 'export') document.getElementById('export').click();
      if (task === 'logout') document.getElementById('logout').click();
    });
    window.addEventListener('popstate', () => {
      const dest = window.location.hash.slice(1);
      if (!directory.some(item => item.tab === dest)) return;
      navigatingBack = true;
      Promise.resolve(window.showTab(dest)).finally(() => { navigatingBack = false; });
    });
  }
  window.addEventListener('DOMContentLoaded', init);
  return {directory, actions, commandSuggestions, exploreView, onPage, showSuggestions};
})();
