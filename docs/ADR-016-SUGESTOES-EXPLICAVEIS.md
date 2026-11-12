# ADR-016 — Próximas ações explicáveis sem automações autônomas

**Decisão:** computar sob demanda até três observações factuais, sem criar uma nova tabela, sem IA paga e sem executar ações. O endpoint autenticado identifica (1) transcrições com sugestões de análise ainda propostas; (2) projetos ativos sem tarefas abertas ou bloqueadas. Cada item possui justificativa e evidência estruturada.

**Alternativas rejeitadas:** duplicar tarefas/retornos já exibidos pela Mesa; gerar alertas persistentes para condições triviais; criar tarefas automaticamente; classificar projetos como urgentes sem evidência; implementar motor geral de regras antes de existir necessidade real.

**Fluxos:** o botão **Revisar** abre o diálogo de transcrição que exige aprovação humana; o botão **Abrir projeto** expõe o contexto para que a pessoa decida se deve criar uma tarefa. Não há deduplicação persistente necessária porque nada novo é gravado. Uma transcrição só volta a ser sugerida enquanto houver itens propostos. As observações podem ser ignoradas sem alterar dados.

**Privacidade:** somente API autenticada, SQL de leitura e HTML escapado. Nenhum envio externo, segredo, configuração paga ou banco paralelo. Limites: até duas transcrições e três projetos candidatos; três resultados exibidos. A avaliação de utilidade ainda depende da homologação humana.