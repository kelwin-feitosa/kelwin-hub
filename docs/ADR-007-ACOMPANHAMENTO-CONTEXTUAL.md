# ADR-007 — Acompanhamentos agrupados por prazo real

**Data:** 2026-11-11 · **Estado:** decisão de baixo custo para uso individual.

## Problema e solução

A lista de oportunidades ordenada por data de criação não indica claramente o que precisa de resposta. A rotina de alerta existente usa dias desde a última interação, mas não prioriza visualmente retornos agendados. Evitamos um CRM completo com estados novos.

`GET /api/opportunities/board` agrupa oportunidades existentes, consultadas no SQLite, em retornos vencidos, próximos 7 dias, mais adiante, aguardando sem prazo, ativos sem prazo e encerrados. Filtros por categoria, status e termo livre funcionam na tela sem requisições extras. Datas são calculadas em UTC para comparações consistentes, sem alterar informações de origem.

**Importante:** o agrupamento não é uma ação: não envia mensagens, não cria contatos e não infere que uma reunião foi confirmada. A oportunidade original mantém seu `status` e `followup_at`; ao atualizar, ela muda de grupo por dados reais. Nenhuma migração ou serviço externo.

## Alternativas descartadas

- Kanban de pipeline completo: acrescentaria superfície sem evidência de uso, além do custo de arraste e controles móveis.
- Regras de IA para decidir próxima ação: desnecessárias para uma classificação por prazo.

## Gates e limites

Testes de segurança e agrupamento por prazo/status, retorno de dados, atualização sem duplicação e interface. Teste real de UX com muitos itens e acessibilidade no navegador do usuário continua pendente.
