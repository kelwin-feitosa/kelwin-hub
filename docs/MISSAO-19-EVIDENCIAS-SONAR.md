# Missão 19 — evidências de análise estática, cobertura e SonarCloud

## Escopo e origem

- GitHub: https://github.com/kelwin-feitosa/kelwin-hub
- Branch analisada inicialmente: `main`; commit `b8cf23fc78eb5012072b1997cc1d36591cf37845` (conferido em 21/11/2026, horário de Brasília)
- Repositório **público** conforme GitHub API naquele momento; a descrição antiga "repositório privado" está desatualizada. A aplicação continua local e guarda o banco em computador pessoal.
- Seis checks verdes naquele SHA: `tests`, `browser`, `accessibility`, `audit`, `CodeQL (python)` e `CodeQL (javascript-typescript)`.
- SonarQube Cloud: https://sonarcloud.io/project/overview?id=kelwin-feitosa_kelwin-hub

## Estado do SonarCloud — evidência não obtida

A UI/API públicas não forneceram o inventário de issues, hotspots, métricas, Quality Gate, branch nem SHA da análise. Sem export ou permissão adequada, **não é possível atribuir IDs de issue, severidades, contagens, métricas de cobertura ou status 'resolvido' ao SonarCloud**.

Não foi ativado um scanner Sonar paralelo. Antes de configurar CI-based analysis ou importar XML, **confirmar se a análise automática está ativa no projeto** e escolher um único modo. A coleta de cobertura Python abaixo funciona independentemente dessa decisão.

Para análise exata, enviar exportação JSON/CSV das issues e hotspots, incluindo regra, severidade, arquivo, linhas, mensagem e status, além de overview do Quality Gate/Measures com data e branch. **Nunca enviar token ou senha.**

## Melhorias independentes executadas nesta PR

1. O workflow CodeQL utiliza SHA de commit fixo para `actions/checkout`, `github/codeql-action/init` e `github/codeql-action/analyze`. O `v4` do CodeQL é uma *tag anotada*: o SHA pinado é o commit efetivo apontado pelo objeto de tag, não o SHA do objeto de tag.
2. `[test]` inclui `coverage>=7,<8`. O workflow principal executa testes sob cobertura de **branch** e coleta `coverage.xml` em formato Cobertura sobre `hub/`, excluindo implicitamente os testes do escopo de produção. O XML é retido como artefato por 7 dias e contém apenas dados de CI sintéticos.
3. Testes de proveniência impedem regressão para tags móveis e verificam a geração do relatório.
4. Nenhum segredo foi criado, nenhuma configuração administrativa foi alterada e nenhum scanner Sonar adicional foi ativado.

## Limitações e próximos gates

- A cobertura **só poderá ser quantificada** a partir da execução completa do novo workflow na PR ou `main`. Não inferir porcentagens pela quantidade de testes.
- O arquivo `coverage.xml` **não entra automaticamente no SonarCloud** sem importação e análise CI devidamente configuradas.
- CodeQL, pip-audit e coverage não substituem revisão contextual de hotspots, testes humanos e threat model.
- Não adicionar check obrigatório de Sonar à ruleset antes de comprovar integração estável.
- Testar recuperação real e instalação no Pop!_OS antes de considerar a versão 1.0 homologada.
