# ADR-011 — Revisão humana de reuniões, evidências e tarefas

**Missão 13.0 (12/11/2026)** — Estágio: implementação local-first, sem provedor de IA obrigatório.

## Decisão

O Hub preserva as transcrições TXT/SRT/VTT da versão 12 como fonte de verdade. A versão 13 introduz:

- **Pacote para ChatGPT** gerado localmente, contendo prompt versionado, um único conteúdo de transcrição, ID, SHA-256 e contexto mínimo do evento. O usuário decide explicitamente quando copiar e compartilhar; o Hub nunca envia dados ao ChatGPT.
- **Importação JSON rigorosa**: `schema_version=1`, `transcript_id`, hash SHA-256, resumo e no máximo 20 itens `action`/`decision`/`question`. Cada evidência usa offsets de caracteres Unicode `[start,end)` e citação literal, verificada contra a transcrição imutável. Nenhum campo externo pode informar `approved`, `task_id` ou comandos.
- **Revisão humana**: itens só se tornam tarefas mediante uma nova chamada autenticada com CSRF e título definido pelo usuário. Projeto/prazo são opcionais e revalidados no backend. Criação e alteração de status ocorrem na mesma transação SQLite. Repetir a conversão retorna a tarefa existente, sem duplicação.
- **Busca privada de trechos** mediante endpoint separado, com resultados limitados e offsets corretos para caracteres acentuados. Transcrições não são expostas pela busca global.
- **Exclusão sob demanda**: a exclusão remove a transcrição e suas análises/itens por cascade de FK, mas preserva tarefas já aprovadas como dados autônomos. A evidência de origem é perdida após exclusão; alertar o usuário. Registros de auditoria sem conteúdo podem permanecer. Backups e arquivos exportados anteriormente não são automaticamente apagados.
- **Nova migração 005** aditiva. Exportação manual JSON inclui os registros de análise/revisão; arquivos exportados contêm dados privados, devem ser protegidos. Backup existente por snapshot inclui o novo esquema.

## Segurança e limitações

1. Não há chamada à API da OpenAI, transcrição ao vivo, bot participante, modelo local obrigatório, pagamento, túnel ou deploy público.
2. Um LLM pode gerar evidências falsas e conclusões erradas. O sistema exige integridade de hash e offsets exatos, mas **isso não prova que a interpretação semântica é correta**. O usuário precisa revisar as propostas.
3. Prazos vindos da IA são apenas sugestões textuais. O usuário informa o prazo no formulário antes da conversão; o Hub valida a data no backend.
4. O botão Copiar pode requerer contexto seguro e permissão de área de transferência; erros são mostrados na interface.
5. A exclusão afeta a cópia ativa no SQLite. Snapshots/backups/exportações anteriores exigem gestão separada. Não prometer apagamento criptográfico garantido do armazenamento físico.
6. `GET /api/meeting-review/search` pesquisa apenas as 250 transcrições mais recentes. O limite protege recursos; retornar cobertura parcial explicitamente.
7. Visualização com dados reais no Pop!_OS ainda depende de homologação; Playwright/Chromium no ambiente de execução anterior encontrou bloqueio de `localhost`.

## MCP e ChatGPT: situação atual

Documentação oficial consultada (12/11/2026):
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

O suporte completo a MCP personalizado no ChatGPT é informado para **Business e Enterprise/Edu**. Pro tem conexão read/fetch, com restrições. ChatGPT não conecta diretamente ao `localhost`; um Secure MCP Tunnel pode existir em produtos compatíveis, mas não está ativado aqui. **Não afirmar suporte de conexão personalizada no Plus** sem uma verificação posterior da conta.

Por isso, a interoperabilidade ChatGPT desta entrega é por **exportação/colagem voluntária e importação de resposta estruturada**, sem custo obrigatório de API. Eventual servidor MCP STDIO local pode ser desenvolvido separadamente e deve ser testado com cliente local antes de qualquer ligação ao ChatGPT.

## Próximos passos

- Revisão da UX em desktop e mobile com navegador real conectado a FastAPI.
- Provedor local/API opcional após autorização, testes semânticos com corpus e orçamento.
- Políticas configuráveis de retenção se houver necessidade demonstrada; exclusão automática sempre desligada por padrão.
- Eventual MCP read-only com permissões mínimas e nenhum endpoint público.
