# Migração entre ambientes e continuidade com o Kelwin Hub original

A direção canônica Java/Spring/PostgreSQL não foi revogada. Este repositório é um piloto temporário para validar UX, fluxo e automação, **não um substituto automático do Hub planejado**.

## Portabilidade local → notebook / servidor

1. Pare a aplicação e preserve o backup criptografado original em local separado.
2. Provisionar o destino e instalar versão compatível.
3. Restaurar snapshot em arquivo novo e validar `PRAGMA integrity_check`.
4. Configurar novos segredos de sessão para o destino (não publicar `.env`).
5. Testar login, contatos, tarefas, alertas e agendamento.
6. Não operar duas instâncias independentes do mesmo banco em paralelo; documentar corte e rollback.

A edição Docker armazena o banco em volume nomeado; o modo nativo usa `./data`. Fazer migração por backup/restauração; a pasta host não é automaticamente compartilhada.

## Possível transição para Java/Spring

Portar contratos de dados: `Project`, `Task`, `Contact`, `Opportunity`, `Event`, `AutomationConfig`, `AutomationRun`, `Alert`, `Audit`. Versionar esquema e status. Converter UUIDs e datas UTC preservando proveniência. Gerar CSV/JSON de exportação com validação de importação (não implementado nesta versão). Testar consistência de referências, deduplicação, agenda, CSRF e alertas antes de desligar o piloto. Não migrar registros de terceiros sem revisão legal.

## Integrações externas

Gmail, Calendar, GitHub e StepFlow permanecem fontes próprias; sincronização futura exige `ExternalReference(provider,type,id,account)` e atualização incremental com reconciliação. EspoCRM só deve ser adotado se o CRM local não atender às necessidades e se a duplicação de responsabilidade for resolvida. n8n deve orquestrar automações, sem assumir a propriedade dos dados de tarefas.
