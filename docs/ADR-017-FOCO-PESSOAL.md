# ADR-017 — Blocos de foco pessoal, sem cronograma profissional automático

**Decisão:** duração estimada opcional nas tarefas e consulta local de encaixe para blocos declarados manualmente. Missão 16.0; verificar CI antes de integrar.

## Contexto

A rotina combina estágio, aulas, estudo, música e projetos pessoais. O Hub deve apoiar sessões curtas sem presumir horário do estágio, capturar dados da S2 ou copiar calendários externos. Agenda/Disponibilidade existentes não equivalem a disponibilidade corporativa.

## Alternativas

- Sem alteração: simplicidade, mas não responde ao que cabe em 30 minutos.
- Novo módulo de planejamento automático ou integração externa: custo e riscos de privacidade injustificados.
- Campo na tarefa + projeção local somente leitura: preserva fonte única, sem calendário duplicado. Escolhido.

## Implementação

- Migração aditiva 008_task_estimate.sql: coluna tasks.estimated_minutes de 5–480 ou NULL; dados anteriores continuam NULL.
- POST/PATCH /api/tasks permitem definir, editar e limpar estimativa; não inferem duração.
- GET /api/focus?minutes=N requer login; N entre 5 e 240; até dez tarefas abertas com estimativa declarada até N, ordenação por prazo, prioridade e duração; informa quantas tarefas abertas não têm estimativa.
- Mesa: bloco de 15/30/60/90 minutos, com acesso explícito à tarefa; não conclui tarefas nem reserva agenda.
- Validação Pydantic e SQLite, HTML escapado, teste HTTP/migração/E2E Chromium.

## Limites

1. Consulta não verifica se realmente há tempo livre; compare com agenda e jornada oficial.
2. Duração é estimativa pessoal, não uma medida de produtividade.
3. Nenhum acesso a e-mail, Teams, Outlook, credenciais, reuniões ou dados corporativos da S2.
4. Não implementa recorrência, sincronização ou calendário paralelo.
5. Não introduz contas externas, telemetria ou custo adicional.

## Atualização segura

A migração é aditiva. Backup criptografado e preflight antes de atualizar banco pessoal; testes de migração de v7 com dados fictícios. Código antigo (v7) não é garantido compatível com um banco já migrado para v8.
