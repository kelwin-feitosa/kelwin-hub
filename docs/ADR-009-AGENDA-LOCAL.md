# ADR-009 — Agenda local com vínculos e proteção transacional de conflitos

**Missão:** Kelwin Hub 12.0 · **Data:** 11/11/2026

## Decisão

Evoluir a tabela `events` existente em vez de construir um serviço externo: migração aditiva `003_event_context.sql` acrescenta `project_id` e `contact_id` com FKs e índices, sem substituir nem excluir eventos antigos. Preservar status confirmados, propostos e cancelados.

A partir desta versão, **somente eventos confirmados** bloqueiam disponibilidade; propostos não reservam horário e cancelados não bloqueiam. Conflito de intervalos é a interseção de `[início, fim)` após normalização UTC: `existing.start < requested.end AND existing.end > requested.start`. Eventos adjacentes não se sobrepõem. O teste ocorre dentro de `BEGIN IMMEDIATE` de SQLite para impedir duas criações concorrentes com mesmo horário. Criação/edição conflituosa retorna HTTP 409; o usuário decide um novo horário. A API autenticada `GET /api/events/conflicts` oferece pré-visualização informativa, mas não substitui o teste transacional.

O formulário permite vincular opcionalmente projeto e contato, ver e alterar horários e estado. A agenda pode filtrar hoje, próximos sete dias ou todos; `GET /api/activity` reutiliza o log existente para histórico de compromissos no contexto vinculado. Não há integração com Calendar/Calendly, envio de e-mail ou publicação de agenda na internet.

## Riscos e limites

- Eventos legados que se sobrepõem permanecem intactos. A política de conflito vale para **novas confirmações/edições**; registros existentes não são cancelados automaticamente.
- A edição de um evento antigo conflituoso pode exigir resolver o conflito antes de confirmar o salvamento; nenhuma correção automática em registros pessoais.
- A regra é local e não conhece agenda externa, deslocamento, preferências de disponibilidade ou múltiplos participantes.
- Fuso padrão de datas sem offset: America/Sao_Paulo, como já fazia o Hub; datas persistidas em UTC.
- Não se trata de ferramenta de reserva pública. Um serviço público futuro precisará de isolamento, autenticação dos administradores, antiabuso e revisão de segurança.
