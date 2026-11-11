# Missão 10.0 — verificação e operações

## Base

- Repositório `kelwin-feitosa/kelwin-hub` privado; base da implementação `main` commit `31f7aac92fcae9c372afa71dc6d5c916f02a966f` com PRs #1–#3 mesclados; CI base 43108720662 aprovada.
- A especificação canônica na Biblioteca, seções 28–30, é visão de produto e requisitos; o código da branch é fonte do status implementado. StepFlow independente.

## Implementação

- Primeira tela **Mesa de trabalho**, sem grid de contadores. Captura rápida com projeto e prazo opcionais; `Q` fora de inputs; acesso a tarefas/projetos/oportunidades relacionados e ações existentes.
- `GET /api/workspace`: tarefas e oportunidades ativas sem tarefa pendente associada, segregação bloqueados, eventos do dia com status proposto/confirmado, alertas locais. Limite a dados já persistidos no SQLite. Não há IA, novos serviços ou alteração de banco.
- CSS renovado com composição editorial e tokens de cor; preserva temas, estados de foco e responsividade. Não utiliza CDN, fontes remotas ou novas dependências JavaScript.

## Comandos de validação

```bash
python -m pytest -q --disable-warnings
python -m compileall -q hub scripts
node --check hub/static/app.js
node tests/ui_sanity.cjs
```

### Controle de regressão

1. `GET /api/workspace` sem login deve ser 401; autenticado mostra tarefas e oportunidades com IDs originais.
2. Oportunidade com tarefa aberta vinculada aparece só pela tarefa; após a tarefa ser concluída, a oportunidade volta como próximo contato sem ser concluída automaticamente.
3. Crie tarefa pela Mesa; verifique em Tarefas, projeto associado e histórico; conclua e confirme que desaparece da Mesa.
4. Alterne projeto/oportunidade a partir da Mesa; o registro correto deve receber foco.
5. Teste proposta vs. confirmação de reunião, fuso horário, teclado (`Q` fora de campos), tema escuro, mobile estreito, exportação, login/logout e alerta.
6. Verifique banco antes/depois; nenhuma migração é requerida nesta versão. Não há delete/rebuild.

### Limitações obrigatórias

- Testes locais Python e semântica JS não são equivalentes a UX real do usuário. O laboratório apresentou **bloqueio administrativo de navegação Chromium para localhost** (`net::ERR_BLOCKED_BY_ADMINISTRATOR`). Foi possível renderizar desktop e mobile com Chromium sobre **respostas fictícias simuladas** e medir ausência de overflow horizontal; essas imagens **não representam execução integrada com backend**.
- Google Calendar, Gmail, GitHub, agendamento público, transcrições de reunião, MCP e IA automatizada seguem **não implementados**.
- Docker e n8n continuam opcionais e ainda não homologados nesta execução.
- A segurança foi avaliada apenas para uso local. Não expor a API ou o banco na rede pública.

## Atualização no Pop!_OS (somente depois de merge na main)

Pare o Hub com Ctrl+C, mantenha uma cópia do banco se já possuir dados relevantes e execute:

```bash
cd ~/kelwin-hub
git status --short
git pull --ff-only
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_local.py
```

**Não execute `scripts/init_env.py` novamente se já tiver `.env`; suas credenciais ficam preservadas.** Não execute demo/simulações no banco real. A instalação atual permanece compatível, sem pacotes extras.

## Próximos passos

- Homologar UI verdadeira no Pop!_OS, testar navegação por teclado e ajustar após feedback.
- Reavaliar navegação lateral e exibição contextual por área após uso real; não reimplementar um dashboard amplo.
- Pesquisar integração Google Calendar read-only somente com escopos mínimos e aprovação. Scheduling, transcrição, MCP e outros apps ficam no backlog sem APIs públicas ativadas.
