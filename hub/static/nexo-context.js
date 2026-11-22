'use strict';
/* NEXO: the database remains the source of truth. Recent contexts are kept
 * only in RAM for the authenticated browser session, never in localStorage/URL. */
window.KelwinNexo = (() => {
  let recent = [];

  function remember(kind, id, title) {
    if (!['projects', 'opportunities'].includes(kind) || !id || !title) return;
    recent = [{kind, id, title}, ...recent.filter(item => !(item.kind === kind && item.id === id))].slice(0, 3);
  }
  function clear() { recent = []; }
  function recentMarkup() {
    if (!recent.length) return '';
    return `<section class="nexo-recent" aria-label="Continuar de onde parei">
      <div class="work-section-heading"><div><h3>Retomar trabalho</h3>
      <p>Contextos abertos nesta sessão; nada é salvo no histórico do navegador.</p></div></div>
      <div class="nexo-recent-list">${recent.map(item =>
        `<button type="button" class="nexo-recent-link" data-nexo-kind="${item.kind}" data-nexo-id="${safe(item.id)}">
          <span>${item.kind === 'projects' ? 'Projeto' : 'Oportunidade'}</span><strong>${safe(item.title)}</strong>
          <span aria-hidden="true">›</span></button>`).join('')}</div></section>`;
  }

  async function showOpportunityContext(id) {
    const region = document.getElementById('opportunity-context-' + id);
    if (!region) return;
    const trigger = document.querySelector(`[data-do="opportunity-context"][data-id="${CSS.escape(id)}"]`);
    if (!region.hidden) {
      region.hidden = true;
      trigger?.setAttribute('aria-expanded', 'false');
      return;
    }
    region.hidden = false;
    trigger?.setAttribute('aria-expanded', 'true');
    region.textContent = 'Carregando informações vinculadas…';
    try {
      const data = await api('/api/opportunities/' + encodeURIComponent(id) + '/context');
      // A stale request must not update the recent-context list after navigation.
      if (!region.isConnected) return;
      remember('opportunities', id, data.opportunity.title);
      const c = data.counts;
      const rows = data.tasks.map(t => `<div class="nexo-task"><div><strong>${safe(t.title)}</strong>
        <small>${safe(t.status)}${t.due_at ? ' · ' + dateTime(t.due_at) : ' · sem prazo'}</small></div>
        ${t.status !== 'done' ? `<button type="button" class="mini" data-do="complete" data-id="${safe(t.id)}">Concluir</button>` : ''}</div>`).join('');
      const notes = data.notes.map(n => `<p><strong>${safe(n.title)}</strong> — ${safe(n.body)}</p>`).join('');
      const audit = data.recent_activity.map(a => `<p><span class="muted">${dateTime(a.at)}</span> · ${safe(a.kind)} · ${safe(a.action)}</p>`).join('');
      region.innerHTML = `<div class="nexo-context-head"><div><h4>Acompanhar esta oportunidade</h4>
          <p>${safe(data.opportunity.contact_name)}${data.opportunity.contact_company ? ' · '+safe(data.opportunity.contact_company) : ''}</p>
          <p>Próxima ação registrada: <strong>${safe(data.opportunity.next_action)}</strong></p>
          <p>${data.opportunity.followup_at ? 'Retorno previsto: '+dateTime(data.opportunity.followup_at) : 'Sem prazo de retorno'}</p>
          <small>${c.open} tarefa(s) aberta(s) · ${c.blocked} bloqueada(s) · ${c.done} concluída(s)</small></div>
        <div class="nexo-actions"><button type="button" class="primary" data-do="add-linked-task" data-id="${safe(id)}">+ Tarefa vinculada</button>
        <button type="button" class="mini" data-do="add-opportunity-note" data-id="${safe(id)}">+ Nota vinculada</button></div></div>
        <div class="nexo-context-grid"><section><h5>Tarefas vinculadas</h5>${rows || '<p class="muted">Nenhuma tarefa vinculada.</p>'}</section>
        <section><h5>Notas da oportunidade</h5>${notes || '<p class="muted">Ainda não há notas vinculadas.</p>'}
        <h5>Histórico realmente registrado</h5>${audit || '<p class="muted">Sem histórico registrado.</p>'}</section></div>`;
    } catch (error) {
      region.textContent = 'Não foi possível abrir o contexto: ' + error.message;
    }
  }

  function init() {
    document.getElementById('content').addEventListener('click', event => {
      const button = event.target.closest('button[data-nexo-kind]');
      if (!button) return;
      const {nexoKind: kind, nexoId: id} = button.dataset;
      if (!['projects', 'opportunities'].includes(kind)) return;
      showTab(kind, id).catch(error => notify('Erro ao navegar: ' + error.message));
    });
  }
  window.addEventListener('DOMContentLoaded', init);
  return {remember, clear, recentMarkup, showOpportunityContext};
})();