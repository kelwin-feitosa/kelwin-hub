# ADR-003 — Mesa contextual como primeira visão operacional

**Data:** 2026-11-11 · **Decisão:** aceitar de maneira incremental, sem substituir páginas especializadas.

## Contexto verificável

O piloto 9.0 tinha como primeira tela um painel de cinco indicadores, listas de tarefas e alertas e uma navegação segmentada por entidades (`Projetos`, `Tarefas`, `Contatos`, `Oportunidades`, `Agenda`, `Automações`). O usuário prefere entendimento rápido e vínculos explícitos, não um dashboard genérico. Uma tarefa ligada a oportunidade/projeto exigia navegação adicional para recuperar contexto. Não há sincronização externa; a fonte de verdade permanece no SQLite local.

## Alternativas (matriz qualitativa, não teste com usuários)

| Conceito | Descobrir a próxima ação | Preservar contexto | Escalabilidade futura | Atrito inicial | Decisão |
|---|---|---|---|---|---|
| A — Mesa contextual: tarefas + retornos, agrupadas por necessidade | Alta | Alta, por junções e links | Alta, projeção somente leitura | Baixo | **Escolhida** |
| B — Linha do tempo de atividades | Boa para itens datados; ruim para pendências sem prazo | Moderada | Boa para reuniões | Médio | Candidata futura |
| C — Espaços de trabalho por projeto | Boa para foco aprofundado em um projeto | Alta | Boa para documentos/colaboração | Alto para visão transversal | Candidata futura |

A direção A é apoiada por padrões publicados: o [Linear/My Issues](https://linear.app/docs/my-issues) prioriza trabalhos importantes e o [Todoist/Quick Add](https://www.todoist.com/help/todoist/features/use-task-quick-add-in-todoist-va4Lhpzz) permite registrar rapidamente tarefas. Adaptamos **conceitos**, não copiados código, interface ou marca.

## Mudanças implementadas

1. `GET /api/workspace`: projeção autenticada, somente leitura, agrupando tarefas em andamento e oportunidades sem tarefas pendentes vinculadas. Ordenação por prazo local, urgência e bloqueio. Eventos do dia mantêm distinção `proposed`/`confirmed` e alertas existentes são apresentados sem duplicar os registros.
2. `hub/workspace.py`: junções SQL com os dados existentes, sem nova tabela, cache ou sincronização. IDs originais alimentam ações já existentes de tarefa/oportunidade. Não há automações ou envios externos adicionais.
3. `hub/static/app.js`: interface inicial **Mesa**, captura rápida de tarefas (projeto e prazo opcionais), ações contextuais e navegação para registro relacionado com foco no alvo. Atalho `Q` fora de campos de entrada; os demais módulos permanecem acessíveis.
4. `hub/static/app.css`, `index.html`: composição editorial focada em ações, sem grid de KPIs, tokens visuais leves e responsivos, contraste de foco, reduzido movimento. Tema claro/escuro; zero bibliotecas externas.

**Sem alteração de esquema:** `PRAGMA user_version` permanece 1. Nenhum ID é duplicado; uma oportunidade reaparece como acompanhamento depois que a tarefa relacionada é concluída, até seu estado/próxima ação ser atualizado pelo usuário. Não inferir automaticamente que concluir tarefa encerra negócio. Nenhuma atualização dos dados antigos é realizada.

## Fluxo e atrito (contagem estrutural, ainda não estudo empírico)

| Ação | Antes (v9) | Agora (v10) |
|---|---|---|
| Registrar tarefa sem projeto | Abrir Tarefas → Nova tarefa → título e opções → salvar | Na Mesa: título → Adicionar |
| Identificar contexto de tarefa na tela inicial | A tela Hoje lista apenas título/prazo/status | Na Mesa, projeto, oportunidade e contato relacionados aparecem na própria linha |
| Retomar oportunidade sem tarefa pendente | Navegar para Oportunidades | Mesa lista próximo passo e oferece criar tarefa/registrar contato |
| Concluir tarefa no início | Botão Concluir no Hoje | Botão Concluir na Mesa (mesmo endpoint) |

Não afirmar tempos reduzidos ou desempenho perceptivo sem testes com usuário e navegador real.

## Limites e decisões de arquitetura

- **Continuar FastAPI + SQLite + HTML/JS/CSS** para a primeira fatia. Custos e risco de migrar para Java/Spring/React/PostgreSQL agora não têm contrapartida observada na escala atual. Direção original mantida como alternativa candidata, sem substituição automática.
- A projeção read-only é um limite lógico simples; não criar camadas de domínio ou event bus antes de haver módulos com regras próprias e casos de uso concretos. Processos externos permanecem sob adaptadores autorizados no futuro.
- Para um agendador próprio: primeiro modelo de disponibilidade e reserva com controle transacional e API separada do serviço privado; frontend público só após auditoria. Para transcrições: ingestão de material consentido, origem, revisão e retenção; não exigir bot presente. Para MCP: endpoints com escopos restritos de leitura e autenticação própria, não expor SQLite. Não foram implementados nesta ADR.
- **StepFlow segue independente**, sem troca de base nem absorção de código. Docker/n8n opcionais, sem nova despesa.
- Limite de software: o método de ordenação é heurístico (prazo, urgência marcada, bloqueio). Não adivinha automaticamente a importância subjetiva. A mesma pessoa pode querer outra organização; validar na máquina do usuário antes de ampliar.

## Segurança, testes e validação

- Autorização no endpoint via `require_login` existente; CSRF preservado em writes, escaping dos campos no frontend. Consultas parametrizadas. Nada sincroniza dados externos.
- Testes novos cobrem 401 anônimo, vínculo tarefa/projeto/contato/oportunidade, não duplicação, pós-conclusão, bloqueios, confirmação de evento, fuso e datas. Testes de navegador simulado inspecionam escaping e fluxos DOM, sem substituir E2E no usuário.
- Critérios de UX: navegação teclado, foco visível, ausência de rolagem horizontal móvel, tema light/dark, evitar texto redundante. Referência de critérios: [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## Seguimento

Validar teclado e fluxo real no Pop!_OS e dispositivo móvel, backup/restauração, densidade para centenas de tarefas. Só então investigar pesquisa, filtros, vistas por projeto, preparação de reuniões e conectores leitura autorizados. Nenhuma ação pública ou serviço pago é parte desta mudança.
