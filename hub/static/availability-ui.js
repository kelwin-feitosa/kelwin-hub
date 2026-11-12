/* Private availability only: confirming a local event rechecks conflicts in /api/events. */
'use strict';
(() => {
  let dialog;
  const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const el=id=>document.getElementById(id);
  const weekdays=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'];
  const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  function mount(){
    if(dialog)return;
    dialog=document.createElement('dialog');dialog.id='availability-dialog';dialog.setAttribute('aria-labelledby','availability-title');
    dialog.innerHTML=`<div class="availability-head"><h2 id="availability-title">Disponibilidade pessoal</h2><button id="availability-close" class="mini" type="button">Fechar</button></div>
      <p class="muted">Somente no seu computador. Nada será publicado para terceiros.</p>
      <section class="availability-section"><h3>Faixas semanais</h3>
        <form id="availability-window-form" class="availability-fields">
          <label>Dia da semana <select name="weekday">${weekdays.map((label,i)=>`<option value="${i}">${esc(label)}</option>`).join('')}</select></label>
          <label>Das <input name="start_time" type="time" value="09:00" required></label>
          <label>Até <input name="end_time" type="time" value="17:00" required></label>
          <button class="primary" type="submit">Adicionar faixa</button>
        </form><div id="availability-windows" aria-live="polite"></div>
      </section>
      <section class="availability-section"><h3>Horários disponíveis</h3>
        <form id="availability-slot-form" class="availability-fields">
          <label>Data <input id="availability-day" type="date" name="day" required value="${today()}"></label>
          <label>Duração <select name="duration"><option value="30">30 min</option><option value="60">60 min</option><option value="90">90 min</option></select></label>
          <label>Intervalo entre reuniões <select name="buffer"><option value="0">Sem intervalo</option><option value="10">10 min</option><option value="15">15 min</option></select></label>
          <button class="primary" type="submit">Mostrar horários</button>
        </form><label class="availability-book-title">Título para nova reunião <input id="availability-event-title" maxlength="180" type="text" placeholder="Reunião de acompanhamento"></label>
        <div id="availability-slots" aria-live="polite"><p class="muted">Consulte uma data para visualizar opções.</p></div>
      </section>
      <p id="availability-error" class="form-error" role="alert" aria-live="assertive"></p>`;
    document.body.appendChild(dialog);
    el('availability-close').addEventListener('click',()=>dialog.close());
    el('availability-window-form').addEventListener('submit',async(event)=>{
      event.preventDefault();const v=Object.fromEntries(new FormData(event.target));
      try{await api('/api/availability/windows','POST',{weekday:Number(v.weekday),start_time:v.start_time,end_time:v.end_time});el('availability-error').textContent='';await listWindows();notify('Disponibilidade adicionada');}
      catch(e){el('availability-error').textContent=e.message;}
    });
    el('availability-slot-form').addEventListener('submit',async(event)=>{event.preventDefault();await loadSlots()});
    el('availability-windows').addEventListener('click',async(event)=>{
      const b=event.target.closest('[data-window-delete]');if(!b)return;
      try{await api('/api/availability/windows/'+encodeURIComponent(b.dataset.windowDelete),'DELETE');await listWindows();el('availability-error').textContent='';}
      catch(e){el('availability-error').textContent=e.message;}
    });
    el('availability-slots').addEventListener('click',async(event)=>{
      const b=event.target.closest('[data-slot-start]');if(!b)return;
      const title=el('availability-event-title').value.trim();
      if(!title){el('availability-error').textContent='Informe o título do compromisso antes de confirmar.';el('availability-event-title').focus();return;}
      b.disabled=true;
      try{await api('/api/events','POST',{title,start_at:b.dataset.slotStart,end_at:b.dataset.slotEnd,status:'confirmed'});
        el('availability-error').textContent='';notify('Compromisso confirmado na agenda local');await loadSlots();}
      catch(e){el('availability-error').textContent=e.message;b.disabled=false;}
    });
  }
  async function listWindows(){
    const data=await api('/api/availability/windows');
    el('availability-windows').innerHTML=data.length?data.map(w=>`<div class="availability-window"><strong>${esc(weekdays[w.weekday])}</strong><span>${esc(w.start_time)}–${esc(w.end_time)}</span><button type="button" class="mini" data-window-delete="${esc(w.id)}">Remover</button></div>`).join(''):'<p class="muted">Configure uma faixa semanal antes de consultar horários.</p>';
  }
  async function loadSlots(){
    const v=Object.fromEntries(new FormData(el('availability-slot-form')));
    el('availability-slots').textContent='Consultando horários…';
    try{
      const data=await api('/api/availability/slots?'+new URLSearchParams({...v,step:'15'}));
      const time=value=>new Date(value).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'});
      el('availability-slots').innerHTML=data.slots.length?data.slots.map(s=>`<button type="button" class="mini availability-slot" data-slot-start="${esc(s.start_at)}" data-slot-end="${esc(s.end_at)}">${esc(time(s.start_at))}–${esc(time(s.end_at))}</button>`).join(''):'<p class="muted">Não há horários livres conforme estas regras.</p>';
      el('availability-error').textContent='';
    }catch(e){el('availability-slots').textContent='';el('availability-error').textContent=e.message;}
  }
  window.KelwinAvailability={open:async()=>{mount();dialog.showModal();try{await listWindows()}catch(e){el('availability-error').textContent=e.message}}};
})();
