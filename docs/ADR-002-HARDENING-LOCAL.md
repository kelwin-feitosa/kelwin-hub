# ADR-002 — Continuidade do núcleo local e endurecimento incremental

**Data:** 11/11/2026 · **Status:** implementada em branch experimental 9.0; **sem merge na main**

## Contexto e decisão

O MVP 7.0 mantém FastAPI, SQLite WAL e frontend sem framework. A investigação 8.0 validou defeitos de entrada, erro 500, logout sem revogação e falha silenciosa do scheduler. Para o cenário real de um usuário, quatro núcleos e cerca de 8 GiB, manter esta pilha, com **migrações SQL incrementais e n8n desligado por padrão**. A direção Java/Spring/Modulith/PostgreSQL/React continua como candidata histórica do documento de requisitos, não foi cancelada; StepFlow não é parte do Hub.

## Garantias introduzidas

1. A API normaliza strings obrigatórias com `strip()` Unicode e responde HTTP 422 para campos vazios; `status:null` é validado antes do SQL.
2. Sessões agora dependem de registro SQLite com revogação por `nonce`; logout revoga o cookie capturado, mesmo se reapresentado por outro navegador. Sessões antigas do 7.0 **não são migradas**: novo login é necessário. A tabela de sessões é mantida localmente (não criptografada separadamente do banco).
3. Versão 1 do esquema (`PRAGMA user_version`) é aditiva; preserva dados antigos (inclusive linhas inválidas existentes), cria tabelas de sessão/diagnóstico e triggers preventivas para novas entradas ASCII em branco. A camada API normaliza também outros espaços Unicode. Nenhum dado legado é corrigido automaticamente.
4. O agendador verifica prazo persistido na inicialização, retomando trabalhos perdidos após suspensão/desligamento. Execuções são idempotentes para alertas abertos por índice único; sem garantias de agendamento em tempo real com computador desligado.
5. Falhas do agendador registram **somente classe da exceção** em `scheduler_health`, log seguro e endpoint autenticado `/api/automation-health`, exibido na UI. Erros que impedem o próprio banco de responder só aparecerão no log do processo.
6. A exportação de dados já existia e o backup criptografado existente é mantido. Restauração sempre em arquivo novo, validada por testes.

## Limitações e riscos aceitos

- `Store` inicializa esquema básico do 7.0 antes da migration 001; novas migrações devem respeitar a série SQL numerada, transações e versão do banco. Fazer **backup cifrado antes de atualizar** a versão de um banco real.
- SQLite em disco local, sem múltiplos workers do uvicorn e sem compartilhamento por rede. Uma instância do scheduler por banco.
- Revogação exige consulta ao SQLite em cada request; proporcional ao uso pessoal; o cookie continua assinado, HttpOnly, SameSite strict e HTTPS-only quando configurado para HTTPS. Reiniciar o serviço não deve revalidar cookies revogados.
- Não há sync OAuth, n8n real, disponibilidade 24/7 nem alerta externo (por desenho).
- Testes locais/HTTP/browser não substituem homologação no Pop!_OS. CI precisa ser observado no GitHub após push, não presumido.

## Revisão

Medir RAM/CPU e validar os fluxos diários no computador-alvo. Revisar necessidade de outro banco, worker dedicado ou infraestrutura remota **somente após requisitos novos e evidências**. Nunca fazer migração destrutiva/automática para PostgreSQL.
