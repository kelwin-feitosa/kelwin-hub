# Kelwin Hub 10.0 — mesa de trabalho contextual (piloto local-first)

> **Estado em 11/11/2026:** primeira fatia vertical implementada e testada por HTTP (sem Docker). A versão 10.0 acrescenta **Mesa de trabalho contextual** e captura rápida sem migração de dados. **Não é o Kelwin Hub completo nem uma substituição aprovada da direção Java/Spring registrada no documento canônico.** Integrações reais com n8n, EspoCRM, Gmail, Calendar e GitHub ainda não foram homologadas.

O Hub é uma central pessoal privada para projetos, tarefas, contatos, oportunidades, agenda e alertas automáticos. Prioriza utilidade antes de infraestrutura complexa. Executa no seu Pop!_OS; os dados são armazenados em SQLite local. n8n é **opcional**, usado apenas quando o fluxo justificar.

## O que está funcionando

- **Mesa (v10.0):** próxima ação unificada por urgência, prazo e bloqueio; contexto de projetos e oportunidades; captura rápida; links diretos e foco; mantém a tela de tarefas, CRM e agenda. Atalho `Q` fora de campos. A visão anterior de estatísticas segue disponível pela API `/api/dashboard`, mas não é mais a tela inicial.
- Arquitetura do novo fluxo: projeção autenticada e somente leitura `/api/workspace`, sem nova tabela ou migração; os dados continuam nos registros existentes. Veja `docs/ADR-003-MESA-CONTEXTUAL.md` e `docs/MISSAO-10-VERIFICACAO.md`.


- Login de usuário único com PBKDF2-SHA256, cookie HttpOnly, SameSite Strict e CSRF ligado à sessão.
- Painel **Hoje** com contadores, tarefas, compromissos locais e alertas.
- Projetos: criar, editar e arquivar/pausar/concluir.
- Contatos: criar e editar, normalização e duplicidade de e-mail.
- Oportunidades: registrar com próxima ação, prazo, valor opcional, status e histórico de contato manual.
- Tarefas: criar, vincular a projeto/oportunidade, editar, concluir e preservar data de conclusão.
- Agenda local: eventos confirmados/propostos e alteração de status.
- Automação do Atlas **A10-02 / A02-04**: detecta oportunidades sem interação por N dias, cria alertas locais e evita duplicidade, com configuração/execução manual/agendada.
- Histórico de execuções, auditoria mínima sem corpo de dados, endpoint interno dedicado para integração futura com n8n.
- Backup consistente e criptografado via Fernet e restauração **em outro arquivo** para evitar sobrescrita acidental.
- Interface responsiva desktop/mobile (sem depender de CDN ou JavaScript remoto).

**Não existem envios automáticos de e-mails, WhatsApp ou outras comunicações para terceiros.**

## 1. Rodar localmente no Pop!_OS (sem Docker)

Exige **Python 3.11+**. Na pasta extraída:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[backup,test]'
python scripts/init_env.py
python scripts/run_local.py
```

1. Crie uma senha forte (mínimo 12 caracteres) quando solicitado. Ela não é salva em texto puro.
2. Abra **http://127.0.0.1:8000** no navegador e use a senha criada.
3. Os dados permanecem no arquivo `data/hub.db` no diretório do projeto.
4. Termine com `Ctrl+C` quando quiser parar; automações deixam de executar com o aplicativo desligado.

**Nunca publique `.env` em repositório ou compartilhe esse arquivo.** Se o Python do sistema não permitir criar o ambiente virtual, instale o pacote de venv da sua distribuição.

### Demonstração fictícia separada

Com o servidor desligado:

```bash
python scripts/demo_scenario.py
HUB_DB_PATH=./data/demo.db python scripts/run_local.py
```

O script cria um banco **isolado**, com pessoa fictícia, oportunidade antiga, tarefa e alerta; não lê suas contas reais. O script recusa sobrescrever `data/demo.db` se já existir. A senha e o segredo continuam os mesmos do `.env` local.

Para retornar ao banco normal, encerre o programa e execute `python scripts/run_local.py` sem o prefixo `HUB_DB_PATH`.

## 2. Rodar com Docker (a homologar no seu equipamento)

Requer Docker Engine e Compose v2. Gere as credenciais primeiro:

```bash
python3 scripts/init_env.py
# Se já gerou .env acima, não repita.
docker compose config --quiet
docker compose up -d --build
```

Acesse **http://127.0.0.1:8000**. O banco reside no volume Docker `hub_data`, diferente do arquivo `./data/hub.db` do modo nativo. **Não alterne entre os dois modos esperando que compartilhem dados automaticamente**; existe plano de migração no documento correspondente.

> Este ambiente de preparação não possui executável Docker. As definições do Compose foram validadas estaticamente; o comando `up` e os testes em contêineres reais permanecem pendentes. Não utilize dados importantes antes dessa homologação.

## 3. n8n opcional (não é requisito do Hub)

Com Docker funcionando e `.env` criado:

```bash
docker compose -f compose.yaml -f compose.n8n.yaml --profile automations config --quiet
docker compose -f compose.yaml -f compose.n8n.yaml --profile automations up -d --build
```

Abra **http://127.0.0.1:5678** e crie seu acesso inicial no próprio n8n. Importe `workflows/stale-opportunities-n8n.json` como um **template ainda não homologado**. Configure manualmente uma credencial HTTP Header Auth com o cabeçalho `X-Hub-Internal-Token` e o valor `HUB_INTERNAL_TOKEN` do `.env`; associe-a ao nó HTTP Request. O destino do nó é `http://hub:8000/api/internal/automations/stale_opportunities/run`, acessível entre contêineres.

**Importante:** a automação do Hub já possui agendamento próprio. Se ativar esse fluxo n8n, desligue o agendador do Hub usando `HUB_SCHEDULER=0` e reinicie o serviço, para evitar execuções redundantes. Mesmo com deduplicação, dois agendadores complicam a observabilidade.

A API interna não modifica contas externas. Não adicione e-mails ou chaves ao JSON do workflow nem exponha a porta n8n para fora de `localhost`.

## 4. Backup criptografado e restauração

### Modo nativo

```bash
python scripts/backup.py backup --db data/hub.db
# Pergunta uma senha de criptografia DIFERENTE da senha do login.
python scripts/backup.py restore --file backups/ARQUIVO.khb --target data/hub-restaurado.db
```

**Mantenha uma cópia do arquivo .khb em outro dispositivo ou armazenamento seguro.** O backup testa a consistência SQLite, mas a restauração deve ser praticada regularmente. **Não perca a senha de backup.** A restauração se recusa a sobrescrever um banco que já existe.

### Modo Docker (backup fora do volume obrigatório)

```bash
docker compose exec hub python scripts/backup.py backup --db /app/data/hub.db --file /app/data/backup.khb
mkdir -p backups
docker compose cp hub:/app/data/backup.khb ./backups/backup.khb
```

O arquivo copiado ainda deve ser protegido e levado a outro equipamento. No modo Docker, a senha de backup é solicitada no terminal do contêiner. **Não substitua manualmente bancos ativos**; faça restauração isolada e teste antes de qualquer migração.

## 5. Testes

```bash
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report -m
node --check hub/static/app.js
```

`node` só é necessário para a verificação de sintaxe JS, não para executar o Hub.

**Testes presentes:** sessão, CSRF, Origin, persistência, dados inválidos, jornada contato → oportunidade → tarefa, edição, agenda, automação configurável, deduplicação concorrente, erro de automação e backup com restauração.

## 6. Segurança e limites

- O servidor nativo escuta em `127.0.0.1:8000`. O Docker publica apenas no mesmo endereço do host.
- **Não exponha** o serviço na rede ou internet sem estudo adicional de TLS, proxy, autenticação e política de acesso remoto.
- `HUB_COOKIE_SECURE=0` é correto somente para HTTP local. Se implantar atrás de HTTPS, reveja o proxy, configure cookie seguro e execute testes reais.
- O agendamento funciona apenas enquanto o aplicativo está ligado, salvo quando migrado para servidor permanente.
- Dados importados de terceiros, integração OAuth, IA local, notificações no celular e sincronização externa **não fazem parte desta versão**.
- É um piloto pessoal, não um produto certificado de segurança. Veja `docs/SEGURANCA.md`.

## 7. Arquivos de decisão e evidências

- `docs/ADR-001-ARQUITETURA.md` — alternativas A/B/C e decisão provisória.
- `docs/HOSPEDAGEM.md` — PC, notebook antigo, servidor, Oracle, Google e acesso remoto.
- `docs/ATLAS_PRIORIZACAO.md` — escolha das automações prioritárias.
- `docs/RELATORIO.md` — o que foi implementado, testado e permanece pendente.
- `docs/SEGURANCA.md` — riscos e limitações antes de dados reais.
- `docs/MIGRACAO.md` — alternância entre ambientes e evolução para o núcleo Java.
- `docs/ui-desktop.png`, `docs/ui-mobile.png` — capturas de interface com respostas **simuladas**, não homologação do backend no navegador.

Este repositório é **um piloto de validação**, sem pretensão de substituir a especificação canônica `Kelwin_Hub_Especificacao_Requisitos.md` da Biblioteca do ChatGPT. Mudanças de direção só se tornam definitivas após avaliação comparativa no Pop!_OS e atualização do documento original.

### Evolução da identidade visual (Missão 11.0)

O tema escuro usa agora superfícies grafite/ardósia e acento azul suave, sem fundos verdes. O favicon local é atendido em `/favicon.ico`; a preferência do sistema orienta o primeiro acesso, e a escolha manual permanece salva no navegador. A decisão e suas limitações estão em `docs/ADR-004-TEMA-ESCURA-FAVICON.md`.
