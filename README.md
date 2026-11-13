# Kelwin Hub — central pessoal local-first

> **Estado verificado em 12/11/2026:** a `main` chegou à **NEXO 14.0** (PRs #22–#25), com Mesa, navegação ÓRBITA, contextos integrados, sugestões locais explicáveis, agenda e revisão humana de reuniões. O código usa **Python/FastAPI + SQLite + HTML/CSS/JS nativos**, por decisão consolidada. O núcleo continua **local-first**, sem dependência de serviços externos. A versão 1.0 **ainda não está homologada**; avaliação humana, instalação em hardware real e auditoria independente permanecem pendentes. A fonte canônica de decisões é `Kelwin_Hub_Especificacao_Requisitos.md` da Biblioteca do ChatGPT.

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

### Pesquisa global e navegação (v11)

Clique em **Buscar** ou use `Ctrl+K` / `⌘K` com o Hub aberto. A pesquisa autenticada usa `GET /api/search?q=...`, procura em projetos, tarefas, contatos, oportunidades e agenda e permite abrir diretamente o registro original. Há busca por nomes relacionados e tolerância a acentos. **Sem internet, API paga ou novo banco.** Veja `docs/ADR-005-BUSCA-UNIFICADA.md`.

### Projetos com contexto (v11)

A seção **Projetos** possui ação **Contexto**: consulte as tarefas vinculadas, seus estados e a próxima tarefa aberta, e crie nova tarefa já associada ao projeto. As informações são consultadas diretamente na base atual pelo endpoint read-only `GET /api/projects/{id}/context`, sem migrações. Veja `docs/ADR-006-PROJETO-CONTEXTUAL.md`.

### Acompanhamentos por prazo (v11)

A seção **Oportunidades** apresenta agora retornos vencidos, da próxima semana, mais distantes, aguardando sem data e encerrados, com filtros de status, categoria e texto. Os grupos vêm de `GET /api/opportunities/board`, apenas leitura, sem criar estados ou alterar datas. Veja `docs/ADR-007-ACOMPANHAMENTO-CONTEXTUAL.md`.

## Missão 12.0 — conhecimento contextual (primeira entrega)

- **Notas locais:** criar, editar, buscar e vincular a projeto, oportunidade e/ou contato. Aparecem na busca global e no contexto dos projetos; sem serviço ou custo de IA.
- **Histórico factual:** `/api/activity?kind=project|opportunity|contact&ident=<uuid>` retorna ações de auditoria realmente registradas e ações de notas/tarefas associadas, com paginação (não cria eventos retroativos imaginários).
- **Migração aditiva versão 2:** preserva todos os registros existentes; teste de atualização a partir do esquema versão 1. O export JSON passa a incluir notas.
- Leia `docs/ADR-008-NOTAS-HISTORICO.md` para limites e escolhas.

## Missão 12.0 — agenda local contextual

- A agenda oferece Hoje / Próximos 7 dias / Todos e edição de título, período e confirmação.
- Horários **confirmados** são protegidos contra sobreposição em transação; tentativas conflitantes retornam HTTP 409. Horários adjacentes são permitidos, propostas não bloqueiam e eventos cancelados não bloqueiam. `GET /api/events/conflicts` permite consulta autenticada.
- `project_id` e `contact_id` opcionais permitem recuperar compromissos no projeto, sem integração externa. A migração versão 3 é aditiva. Veja `docs/ADR-009-AGENDA-LOCAL.md`.

## Missão 12.0 — transcrições locais autorizadas

- Importar transcrições já existentes de reuniões TXT, SRT ou VTT (até 200 KB UTF-8) na Agenda; consultar origem e conteúdo, incluindo marcas de tempo explícitas para legendas. Tudo permanece no SQLite local.
- Nenhuma gravação ou participação de bot é feita; nenhuma IA é chamada. Texto da transcrição é não confiável e não gera automaticamente tarefas, compromissos ou mensagens. A exportação JSON agora pode conter texto de reuniões e deve ficar protegida. Consulte `docs/ADR-010-TRANSCRICOES-LOCAIS.md`.
- A migração versão 4 é aditiva e não exige reconfiguração de senha.


## Missão 13.0 — Revisão de reuniões (local-first)

Em Agenda → Transcrições → Ler → **Preparar e revisar análise**, o Hub prepara um pacote que pode ser copiado voluntariamente para o ChatGPT. Você decide se compartilhará o conteúdo privado. O Hub não envia nada automaticamente. Cole o JSON de retorno, confira as evidências literais e aprove cada ação individualmente para gerar tarefa (não há tarefa criada por análise sem aprovação). Sugestões sem evidência exata são rejeitadas; imports repetidos e aprovação repetida não duplicam tarefas. Busca específica: `/api/meeting-review/search?q=...`. Há exclusão explícita de transcrições por API autenticada; isso remove também análises/itens vinculados, porém não elimina backups antigos ou tarefas aprovadas. A documentação de segurança e limites está em `docs/ADR-011-REVISAO-REUNIOES.md`. Não exige IA paga, bot nem servidor MCP remoto.


## Missão 13.0 — Disponibilidade local

Na Agenda, escolha **Horários livres** para cadastrar faixas semanais, consultar opções livres em `America/Sao_Paulo`, considerar duração e intervalo entre compromissos, e confirmar um evento **local**. O preview ignora propostas e cancelamentos e considera apenas eventos confirmados do próprio Hub. A confirmação passa novamente pela API `/api/events`, com transação e prevenção de conflitos. Nenhuma disponibilidade é criada por padrão e nenhum horário é publicado para terceiros. Não há sincronização externa nem reserva pública. Veja `docs/ADR-012-DISPONIBILIDADE-PRIVADA.md`.


**Missão 13.0 — Citações práticas:** ao importar resultado de ChatGPT, basta enviar `evidence.quote` com um trecho literal **único** da transcrição. `evidence.start` e `evidence.end` são opcionais: o Hub localiza offsets Unicode quando o trecho é único. Citações inexistentes/ambíguas são rejeitadas. Na revisão, é possível pesquisar outras transcrições e excluir o conteúdo após confirmação; backups/exportações anteriores permanecem sob gestão do usuário.


## Missão 13.6 — Navegação ÓRBITA

A navegação principal possui quatro destinos estáveis: **Mesa, Projetos, Agenda e Explorar**. As oito áreas originais continuam no catálogo **Explorar** e no iniciador **Buscar / Ctrl+K**, que combina resultados do endpoint local de busca com destinos e ações de criação sem nova API. O botão **Novo** abre a mesma busca filtrada para criação. No celular, a navegação usa um dock inferior com quatro áreas, evitando a faixa horizontal rolável; exportação e encerramento da sessão permanecem disponíveis em Explorar. Nenhuma migração ou serviço pago foi adicionado. Ver `docs/ADR-013-NAVEGACAO-ORBITA.md`.


### NEXO 14.0 — Índices de contexto

A migração **007** acrescenta índices para consultas de tarefas por projeto e oportunidade, sem excluir nem transformar registros. O esquema é atualizado transacionalmente pelo mecanismo existente na primeira abertura após atualização. O benchmark sintético reproduzível pode ser executado com `python scripts/benchmark_nexo_indexes.py`; resultados não representam o desempenho da máquina do usuário. Antes de atualizar um banco com registros importantes, faça backup. Detalhes em `docs/ADR-015-INDICES-CONTEXTO-NEXO.md`.


### NEXO — observações locais explicáveis

A Mesa apresenta no máximo três sugestões factuais: revisão humana de itens importados de reunião e projetos ativos sem tarefas abertas. Ações continuam explícitas, sem criar tarefas ou tomar decisões automaticamente. Ver ADR-016.

## Operação HORIZONTE 15.0 — verificações de integridade (em desenvolvimento)

- Validação de `value_brl`: aceita formato decimal não negativo com até dez dígitos inteiros e duas casas, recusando expoentes, valores não finitos e entradas excessivas antes da conversão numérica.
- Backup/restauração: além de `integrity_check`, exige `PRAGMA foreign_key_check` sem violações para não exportar nem publicar um banco com vínculos corrompidos.
- Testes de regressão com dados sintéticos foram adicionados; considerar a implementação aprovada somente após CI verde no SHA correspondente.

### HORIZONTE — diagnóstico de segurança e atualização

Com o Hub **desligado**, execute na raiz do projeto, antes de atualizar:

```bash
python scripts/preflight.py
```

O comando **não aplica migrações nem grava no SQLite**. Ele confere estrutura e integridade, versão do esquema, permissões do `.env` e do banco, sem imprimir senhas ou registros. A saída pode indicar `ok`, `warning` (corrija as ressalvas) ou `error` (não prossiga antes de investigar). Caso use um caminho diferente do padrão, passe `--db /caminho/para/hub.db`.

Antes da atualização, ainda é obrigatório fazer backup criptografado, mantê-lo fora da pasta principal e verificar a restauração em banco separado. O launcher nativo cria novos bancos com permissão 0600 e endurece bancos existentes no Linux, sem substituir dados. Para bancos existentes, confirme que não há outra instância em execução. Isso não protege contra usuários com acesso privilegiado nem substitui criptografia do disco.

### HORIZONTE — lista de tarefas paginada

A seção **Tarefas** usa `GET /api/tasks/page?limit=30&offset=0&status=all&q=`, com máximo de 100 itens por resposta, contagem real, ordenação estável e filtros de status/título. Busca textual trata caracteres `%` e `_` literalmente. A interface oferece **Anterior / Próxima**, estado vazio e controles para teclado e telas pequenas. O endpoint antigo `GET /api/tasks` permanece para compatibilidade com integrações internas existentes; não usá-lo para renderizar listas grandes. A filtragem de título utiliza SQLite `lower` básico, sem prometer equivalência de acentos Unicode.

## Missão 16.0 — blocos de foco pessoal

Na **Mesa**, escolha voluntariamente um bloco de 15, 30, 60 ou 90 minutos. O Hub mostra tarefas **abertas** cuja **duração foi cadastrada explicitamente** e não excede o bloco. A criação e a edição de tarefas permitem estimativa opcional de 5 a 480 minutos.

A migração aditiva **008** preserva tarefas anteriores com duração desconhecida (NULL). O endpoint autenticado GET /api/focus?minutes=30 é somente leitura e devolve até dez opções. Não envia informações externas, não registra atividade e não reserva horário.

**A consulta não comprova que existe tempo livre**, pois o horário definitivo do estágio não foi importado nem foi autorizado acesso ao calendário da S2. O Hub permanece pessoal: metas de aprendizado e horários genéricos podem ser cadastrados voluntariamente; dados internos da empresa, credenciais e transcrições precisam de autorização adequada.

Veja docs/ADR-017-FOCO-PESSOAL.md.
