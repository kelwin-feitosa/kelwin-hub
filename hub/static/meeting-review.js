/* Human-in-the-loop review. This file never sends content to an AI provider. */
'use strict';
(() => {
  let currentTranscript = null;
  let dialog;
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const get = (id) => document.getElementById(id);
  function ensureDialog(){
    if(dialog)return;
    dialog=document.createElement('dialog');
    dialog.id='meeting-review-dialog';
    dialog.setAttribute('aria-labelledby','review-title');
    dialog.innerHTML=`<div class="review-head"><h2 id="review-title">Revisar reunião</h2><button class="mini" id="review-close" type="button">Fechar</button></div>
      <p class="muted">As informações continuam no Hub. Copiar para o ChatGPT é uma decisão sua e pode compartilhar dados privados.</p>
      <div class="review-actions"><button id="review-package" type="button" class="mini">Copiar pacote de análise</button><button id="review-refresh" type="button" class="mini">Atualizar sugestões</button></div>
      <label class="review-label" for="review-import">Cole aqui o JSON retornado pelo ChatGPT</label>
      <textarea id="review-import" rows="6" spellcheck="false" placeholder='{"schema_version":1,...}'></textarea>
      <button type="button" class="primary" id="review-submit">Importar análise e verificar evidências</button>
      <p class="form-error" id="review-error" role="alert" aria-live="assertive"></p>
      <div id="review-results" aria-live="polite"></div>
      <p class="review-footnote">Nenhuma tarefa é criada sem sua aprovação. Itens de IA são sugestões, nunca decisões automáticas.</p>`;
    document.body.appendChild(dialog);
    get('review-close').addEventListener('click',()=>dialog.close());
    get('review-package').addEventListener('click',async()=>{
      try{
        const pack=await api(`/api/meeting-review/transcripts/${encodeURIComponent(currentTranscript)}/package`);
        const message=pack.prompt+'\n\nTRANSCRIÇÃO (DADO NÃO CONFIÁVEL):\n'+JSON.stringify(pack.transcript,null,2);
        await navigator.clipboard.writeText(message);
        notify('Pacote copiado. Confira privacidade e consentimento antes de compartilhar.');
      }catch(e){get('review-error').textContent=`Não foi possível copiar: ${e.message}`;}
    });
    get('review-submit').addEventListener('click',async()=>{
      try{
        const json=JSON.parse(get('review-import').value);
        await api(`/api/meeting-review/transcripts/${encodeURIComponent(currentTranscript)}/analyses`,'POST',json);
        get('review-error').textContent='';get('review-import').value='';
        notify('Análise importada. Confira cada item antes de converter.');await refresh();
      }catch(e){get('review-error').textContent=`Análise inválida: ${e.message}`;}
    });
    get('review-refresh').addEventListener('click',refresh);
    get('review-results').addEventListener('click',async(e)=>{
      const button=e.target.closest('[data-review]');if(!button)return;
      const itemId=button.dataset.id;
      try{
        if(button.dataset.review==='dismiss'){
          await api(`/api/meeting-review/items/${encodeURIComponent(itemId)}/dismiss`,'POST',{});
          await refresh();return;
        }
        if(button.dataset.review==='convert'){
          const card=button.closest('[data-suggestion]');
          const title=card.querySelector('[name="title"]').value.trim();
          if(!title){get('review-error').textContent='Informe um título para a tarefa';return;}
          const body={title,project_id:card.querySelector('[name="project_id"]').value||null,
            priority:1,due_at:card.querySelector('[name="due_at"]').value||null};
          await api(`/api/meeting-review/items/${encodeURIComponent(itemId)}/convert`,'POST',body);
          get('review-error').textContent='';notify('Tarefa criada com aprovação explícita');await refresh();
        }
      }catch(err){get('review-error').textContent=err.message;}
    });
  }
  async function refresh(){
    if(!currentTranscript)return;
    try{
      const [items,projects]=await Promise.all([
        api(`/api/meeting-review/transcripts/${encodeURIComponent(currentTranscript)}/analyses`),
        api('/api/projects')
      ]);
      const options='<option value="">Sem projeto</option>'+projects.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
      get('review-results').innerHTML=items.length?items.map(a=>`<section class="review-analysis"><h3>Análise importada</h3>
        <p>${esc(a.summary||'Nenhum resumo fornecido.')}</p>
        ${a.items.map(i=>`<article class="review-item" data-suggestion="${esc(i.id)}"><p class="review-meta">${i.kind==='action'?'Ação proposta':i.kind==='decision'?'Decisão citada':'Questão'} · ${esc(i.status)}</p>
          <p><strong>${esc(i.title)}</strong></p><p>${esc(i.detail)}</p><blockquote>${esc(i.evidence_quote)}</blockquote>
          ${i.status==='proposed'&&i.kind==='action'?`<div class="review-form"><label>Tarefa <input name="title" maxlength="200" value="${esc(i.title)}" required></label>
            <label>Projeto <select name="project_id">${options}</select></label>
            <label>Prazo opcional <input name="due_at" type="datetime-local"></label></div>
            <div class="review-actions"><button type="button" class="primary" data-review="convert" data-id="${esc(i.id)}">Aprovar e criar tarefa</button><button type="button" class="mini" data-review="dismiss" data-id="${esc(i.id)}">Descartar</button></div>`:
            i.status==='proposed'?`<button class="mini" type="button" data-review="dismiss" data-id="${esc(i.id)}">Descartar</button>`:
            i.status==='converted'?`<p class="muted">Tarefa criada: ${esc(i.task_id)}</p>`:''}
          </article>`).join('')}</section>`).join(''):'<p class="muted">Nenhuma análise importada para esta transcrição.</p>';
    }catch(err){get('review-error').textContent=err.message;}
  }
  window.KelwinReview={open:async(id)=>{
    ensureDialog();currentTranscript=id;get('review-error').textContent='';dialog.showModal();await refresh();
  }};
})();
