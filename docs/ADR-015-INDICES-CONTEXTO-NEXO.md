# ADR-015 — Índices de tarefas para contextos NEXO

**Status:** proposta implementada com migração aditiva 007, testes de preservação e benchmark sintético reproduzível.

## Problema

Os dois novos fluxos de contexto leem tarefas filtrando por `project_id` e `opportunity_id`. O esquema v6 indexava apenas `tasks(status,due_at)`, não as chaves estrangeiras dessas consultas. Com grandes volumes, SQLite precisava percorrer a tabela inteira.

## Evidência

Experimento isolado com SQLite em Linux, CPU da instância de teste, dados completamente fictícios e 150 execuções por cenário, `cached_statements=0` e massas de 500/5.000/20.000 tarefas. Comparação da mesma consulta, com e sem índice:

| Tarefas | Mediana sem índice | Mediana com índice | p95 sem índice | p95 com índice |
|--:|--:|--:|--:|--:|
| 500 | 0,038 ms | 0,0187 ms | 0,0574 ms | 0,0314 ms |
| 5.000 | 0,3177 ms | 0,0756 ms | 0,4874 ms | 0,1540 ms |
| 20.000 | 1,2985 ms | 0,3211 ms | 2,0583 ms | 0,4915 ms |

Esses valores são **microbenchmarks de SQL isolado**, não latência HTTP, nem medição no Pop!_OS. Repetições, cache do SO e hardware influenciam resultados. O código para replicação está em `scripts/benchmark_nexo_indexes.py`. `EXPLAIN QUERY PLAN` passou de `SCAN tasks` para `SEARCH tasks USING INDEX task_project_context_idx (project_id=?)`.

## Decisão

Migração 007 cria `task_project_context_idx` e `task_opportunity_context_idx` com `CREATE INDEX IF NOT EXISTS`. Sem nova tabela, sem alteração das entidades, sem remoção de registros. Índices aumentam ligeiramente o custo de escrita e espaço em disco; o benefício justifica-se pelo padrão de leitura contextual.

O endpoint de oportunidade retorna até 60 tarefas para evitar DOM excessivo; os totais agora são calculados separadamente de todo o conjunto, e `truncated_tasks` identifica quando a lista foi limitada.

## Segurança e compatibilidade

Migração versionada transacional pelo mecanismo existente do Store. Testes constroem esquema real até v6, preservam registros e reabrem v7. Dados e `.env` do usuário não são tocados por esta execução.

## Referência

SQLite Query Planner e EXPLAIN QUERY PLAN: https://www.sqlite.org/eqp.html