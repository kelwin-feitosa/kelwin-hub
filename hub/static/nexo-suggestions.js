'use strict';
/* Suggestions do not approve a meeting proposal or mutate anything. */
window.KelwinSuggestions = {
  render(items) {
    if (!Array.isArray(items)) return '';
    const cards = items.slice(0, 3).map(item => {
      const isReview = item.kind === 'meeting_review';
      if (!isReview && item.kind !== 'project_next_step') return '';
      const action = isReview ? 'review-transcript' : 'open-project';
      return `<article class="nexo-suggestion"><div><strong>${safe(item.title)}</strong>
        <p>${safe(item.reason)}</p></div><button type="button" class="mini"
        data-do="${action}" data-id="${safe(item.id)}">${isReview ? 'Revisar' : 'Abrir projeto'}</button></article>`;
    }).filter(Boolean).join('');
    return cards ? `<section class="nexo-suggestions" aria-label="Possíveis próximos passos">
      <header><h3>Para considerar</h3><p>Observações baseadas em registros locais. Nenhuma ação é automática.</p></header>
      ${cards}</section>` : '';
  },
};