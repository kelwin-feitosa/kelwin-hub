# Kelwin Hub 9.0 — Plano de verificação e instalação local

## Estado e escopo

Branch de 9.0 derivada de `feat/kelwin-hub-7-mvp` (`db111d251460f3ded8e3b32d4aaea589bf5f245f`), sem merge em `main`. Defeitos do relatório 8.0 convertidos em regressões antes das correções. Testes usam dados fictícios. **Não declarar Docker/n8n/Pop!_OS homologados sem execuções correspondentes**.

## Instalação no Pop!_OS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,backup]'
python -m pytest -q
python scripts/init_env.py
# Cria .env no diretório local, com senha e segredos fora do git; reveja os campos.
python scripts/run_local.py
```

Acesse apenas `http://127.0.0.1:8000`; verifique a origem em `scripts/run_local.py`. Não coloque `.env`, `data/`, `backups/`, `.khb` ou logs privados no GitHub. Não habilite portas públicas. Não instale Docker/n8n para o MVP se não precisar de fluxos externos.

## Atualização v7 → v9

1. **Pare o serviço anterior.** Faça backup cifrado e guarde senha em local seguro, fora do diretório do repositório.
2. **Faça cópia de teste da base** e execute v9 sobre a cópia. A inicialização aplica migration SQL `001` e ajusta `PRAGMA user_version` para `1` em transação. Nunca reconstrua ou apague as tabelas de dados como passo automático.
3. Confira `PRAGMA integrity_check`, contagem de contatos/oportunidades/tarefas, login, sessão, logout e `/api/automation-health`. Sessões emitidas na v7 precisarão de novo login.
4. Com o sistema parado, aplique a atualização ao banco real e verifique as contagens novamente; se necessário, volte ao backup em outro destino, sem sobrescrever arquivo existente.

## Comandos de validação

```bash
python -m pytest -q --disable-warnings
python -m compileall -q hub scripts
node --check hub/static/app.js
python scripts/backup.py backup --db data/hub.db --file backups/teste.khb
python scripts/backup.py restore --file backups/teste.khb --target data/restaurado.db
```

O backup pede senha via terminal; nunca a guarde em arquivo de configuração ou histórico do shell. Verifique `.khb` criptografado e o arquivo restaurado. Apague **somente** os arquivos de teste após verificar que não contêm dados pessoais.

## Aceitação de UX e automação

1. Criar contato; criar oportunidade com título, próxima ação e data de retorno.
2. Na oportunidade, selecionar **Criar tarefa** e confirmar que título e prazo foram pré-preenchidos; concluir tarefa a partir do painel **Hoje**.
3. Selecionar **Registrar contato** e conferir o histórico de auditoria; executar a automação, verificar idempotência e ausência de alertas repetidos.
4. Suspender/reiniciar a máquina e verificar execução de catch-up em até um ciclo do agendador, sem notificação externa.
5. Confirmar que `/api/automation-health` apresenta horário da última checagem e classe de erro quando houver falha.
6. Navegar por teclado, testar desktop/celular reais e compatibilidade com navegador; testar acessibilidade com leitor de tela se aplicável.

## Próximos gates

- **G1 validável:** regressões HTTP + migração/backup + logs e health + CI real.
- **G2 pendente:** review de segurança de deploy, proxy/HTTPS se acesso remoto for autorizado, testes em hardware do usuário.
- **G3 pendente:** n8n Community em contêiner real, medição de RSS e validação de API oficial — opcional, não bloqueia Hub.
- **G4 pendente:** conector read-only Google Calendar sob OAuth (somente após caso de uso e autorização), depois Gmail/GitHub.
- **G5 pendente:** Atlas A01-02 de projetos sem avanço e A02-02 preparação de reuniões, após uso real provar benefício.