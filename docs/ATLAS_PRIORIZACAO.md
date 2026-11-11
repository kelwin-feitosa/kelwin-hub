# Atlas Universal das Automações aplicado ao Kelwin Hub

Fonte: `Atlas_Universal_Automacoes_2026.md` e `Atlas_240_Automacoes_2026.xlsx` na Biblioteca. O catálogo original apresenta **240 ideias, 30 domínios e rankings exploratórios**. Não são automações já implementadas, e as notas não substituem testes.

## Seleção de automações priorizadas

| ID | Automação | Benefício pessoal | Fonte / dependência | Fase | Estado |
|---|---|---|---|---|---|
| **A10-02** | Detector de cliente órfão | Não esquecer contatos e oportunidades | Dados locais, regra de prazo | **MVP** | **Implementada e testada** |
| **A02-04** | Lembrete por dependência | Recuperar retornos esperados | Oportunidade local + data | MVP parcial | Compartilha o mesmo alerta A10-02, ainda não examina e-mails |
| **A01-01** | Captura universal de pendências | Registrar tarefas rapidamente | Entrada manual, texto | P1 | Captura manual existe; extração de áudio/texto não |
| **A01-02** | Detecção de projetos abandonados | Reativar projetos parados | Data de atividade | P1 | Planejada |
| **A02-02** | Preparador de reuniões | Chegar com contexto | Calendar/Drive autorizado | P2 | Template planejado |
| **A05-01** | Promessas não registradas | Não esquecer compromissos | E-mail/nota consentida | P2 | Planejada |
| **A09-02** | Propostas sem retorno | Recuperar oportunidades de renda | CRM + valor/prazo | P1 | Planejada |
| **A09-04** | Gerador de proposta por escopo | Ganhar tempo em orçamentos | Templates/entrada manual | P2 | Planejada |
| **A06-01** | Triagem por ação | Priorizar caixa de entrada | Gmail OAuth | P2 | Planejada |
| **A15-08** | Detector de segredos | Prevenir vazamento nos commits | Git/pre-commit | P1 | Planejada |
| **A16-08** | Falha silenciosa | Saber quando um job parou | Heartbeat/agendador | P1 | **Parcial:** erro persistido, detecção de ausência ainda não |
| **A17-03** | Vencimento documental | Evitar perder prazos | Registro local | P2 | Planejada |

### Critérios para passar de planejado a implementado

Cada template precisa definir `gatilho → condição → ação → evidência`, custo, permissions, dry-run e capacidade de desativar. Integrações dependentes de serviços externos só entram após consentimento, teste de falhas, cotas e proveniência. A categoria "IA" não é gatilho de adoção: comparar regra simples primeiro.

### MVP real

Uma automação: **A10-02 com critério de espera do A02-04**. Usuário escolhe período em dias, ativa/desativa, executa manualmente ou deixa o Hub verificar periodicamente. Para oportunidade aberta sem contato no período, cria alerta local, deduplicado e com histórico. Marcando contato, o alerta é resolvido. Ao dispensar, permanece silencioso até haver uma nova interação registrada.

Não envia mensagens; não lê Gmail; não acessa Google Calendar; não altera contas externas.
