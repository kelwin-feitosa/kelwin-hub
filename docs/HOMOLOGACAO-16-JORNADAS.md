# Missão 16 — matriz substituta A–O de homologação

**Origem:** matriz operacional reconstruída para validar o núcleo atual; **não é uma reprodução comprovada** das jornadas A–O históricas, que não foram recuperadas integralmente nesta execução. Foi criada a partir do repositório e dos testes existentes. Não duplicar a especificação canônica.

**Legenda:** Automatizado = existe teste verificável no CI; Manual = deve ser realizado pelo usuário no equipamento pessoal; Pendente = cenário específico ainda não completamente coberto. Teste verde não transforma homologação manual em aprovado.

| Jornada | Fluxo | Evidência de teste automatizado | Manual / risco residual |
|---|---|---|---|
| A | Primeiro acesso, login, logout e sessão revogada | tests/test_end_to_end.py; tests/test_hub9_regressions.py | Confirmar inicialização e login pessoal |
| B | Proteção CSRF, Host, Origin e sessões | tests/test_end_to_end.py; tests/test_trusted_hosts.py; tests/test_orbita_security.py | Auditoria independente e hardening do OS |
| C | Criar, editar e arquivar projetos | tests/test_end_to_end.py; tests/test_nexo_context.py | Avaliar clareza da interface |
| D | Contatos e normalização/duplicidade | tests/test_end_to_end.py | Confirmar critérios de retenção de dados de terceiros |
| E | Oportunidades e acompanhamento manual | tests/test_end_to_end.py; tests/test_opportunity_board.py | Conferir uso real comercial |
| F | Tarefas, prioridade, estimativa e conclusão | tests/test_focus_personal.py; tests/test_horizonte_task_pages.py | Validar planejamento de 15/30/60/90 min com rotina real |
| G | Busca global e ações de comando | tests/test_search.py; tests/orbita_ui_sanity.cjs | Testar teclado e leitores de tela |
| H | Notas e histórico contextual factual | tests/test_notes_activity.py; tests/test_nexo_context.py | Avaliar recuperação após mudanças |
| I | Agenda com conflitos e estados | tests/test_agenda_conflicts.py; tests/test_end_to_end.py | Conferir calendário real e fuso |
| J | Disponibilidade privada e horários indicativos | tests/test_availability.py; tests/browser_orbita_e2e.py | Não presumir compromissos da S2 |
| K | Importação de TXT/SRT/VTT autorizados | tests/test_transcripts.py | Conferir retenção e autorização |
| L | Revisão de transcrição com citações e aprovação explícita | tests/test_meeting_review.py; tests/browser_nexo_e2e.py | Interpretação humana da IA permanece obrigatória |
| M | Automações locais, deduplicação e falhas | tests/test_end_to_end.py | Estabilidade em reinício prolongado ainda pendente |
| N | Backup cifrado e restauração isolada | tests/test_backup_hardening.py; tests/test_release_recovery.py | Restaurar backup **pessoal** com supervisão local |
| O | Migração v7→v8, falha intermediária e integridade | scripts/rehearse_upgrade.py; tests/test_release_recovery.py | Homologar upgrade de instalação pessoal real |

## Evidências e limites

- A CI principal inclui Pytest, FastAPI TestClient, banco SQLite real com dados sintéticos, Chromium/Playwright, axe-core, auditoria de dependências, ensaio de upgrade e benchmark HTTP informativo.
- Os testes não comprovam disponibilidade contínua 24/7, resistência a todas as falhas de energia, cobertura OWASP ASVS total, pentest, sincronização corporativa ou experiência real em outra distribuição Linux.
- Não se deve invocar G15 como aprovado sem avaliação do usuário. Recomenda-se registrar no documento canônico quais jornadas foram testadas manualmente, qual versão/commit e quaisquer defeitos.

## Métricas reproduzíveis

Executar: python scripts/benchmark_http.py --tasks 1000 --iterations 20

Este script usa um SQLite temporário, gera tarefas fictícias e mede tempo total HTTP via FastAPI TestClient (p50 e p95 por rota) e bytes de resposta em quatro endpoints. Não há rede externa e nenhum dado pessoal é aberto.

Não interpretar tasks_page versus tasks_all_legacy como melhoria percentual diretamente equivalente: os endpoints devolvem quantidades diferentes de registros. Comparações causais antes/depois exigem código, ambiente, carga e resposta equivalentes. O benchmark **não mede** renderização do navegador, CPU/memória do Pop!_OS pessoal, nem experiência humana.

## Segurança: referência e não certificação

A inspeção foi orientada por categorias relevantes da documentação oficial OWASP ASVS 5.0 (https://asvs.owasp.org/) e pela documentação SQLite WAL (https://www.sqlite.org/wal.html), sem alegar verificação item a item, certificação ou pentest. Pontos residuais: duração de sessão, política de logs, arquivos auxiliares, retenção, cópias pessoais, uso em volume compartilhado e autenticação resistente a uso remoto. O Hub permanece local-only, mono-usuário e não apto à exposição pública.
