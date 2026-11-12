# FORJA 13.5 — auditoria de qualidade e desempenho (12/11/2026)

## Escopo e evidências

Repositório: `kelwin-feitosa/kelwin-hub`. Estado de entrada confirmado: `ea0ed5b46851206cf385ee8417e73772752ebb7a`, 84 testes aprovados no GitHub Actions e nenhum PR aberto. A auditoria inspecionou módulos críticos de segurança, storage/migrações, automações, disponibilidade, revisão de reuniões, pesquisa global, rotas FastAPI, backup, scripts de teste e workflow. **Não se afirma auditoria exaustiva linha a linha de todos os recursos frontend.**

### Prioridades e conclusões

| Prioridade | Evidência | Ação |
|---|---|---|
| P1 integridade/backup | `scripts/backup.py` publicava o arquivo cifrado depois de uma checagem `exists` e usava `Path.replace` na restauração; uma alteração concorrente do destino poderia ser sobrescrita | PR #16: criação exclusiva e restauração com publicação `os.link`, não sobrescrevendo destino; ZIP limitado e extração em fluxo; 4 novos testes |
| P1 disponibilidade/desempenho | `hub/search.py` alocava todos os candidatos em memória antes de iterar e recalculava `folded(query)` por resultado. `limited` não informava quando só o limite por tipo era atingido | PR #17: iterador SQL, pré-normalização, cálculo de contexto sob demanda, correção de `limited`, benchmark e regressão |
| P2 CI/manutenção | Workflow usa versões de actions baseadas no Node20, com aviso de descontinuação em runner | PR #17: atualizar actions de primeira parte para versões Node24 compatíveis, validar pela CI |
| P2 arquitetura | `hub/api.py` agrega diversos endpoints e validações; há módulos específicos de agenda, disponibilidade, pesquisa e revisão | Não executar reescrita grande sem testes e responsabilidade delimitada; registrar recomendação de extração incremental |
| P2 qualidade de testes | Aprovações e conflitos possuem testes de concorrência, mas a navegação real Chromium–FastAPI segue bloqueada no ambiente de execução | Preservar testes de API e scripts de navegador; exigir E2E real em ambiente compatível antes de homologação |

## Benchmark de pesquisa

Método: SQLite temporário com **7.000 registros fictícios** distribuídos em 800 projetos, 4.500 tarefas, 300 contatos, 600 oportunidades, 600 notas e 200 eventos. Sete consultas representativas, doze ciclos intercalados entre o algoritmo anterior e o otimizado no mesmo processo. 84 amostras por variante, mesmo equipamento; comparação de listas de resultados confirmou os mesmos registros e mesma ordem. Pico de memória de uma consulta medido com `tracemalloc`; o sinal `limited` ganhou significado mais correto, sendo a única mudança funcional intencional.

| Métrica | Antes | Depois | Variação observada |
|---|---:|---:|---:|
| Mediana de busca | 94,07 ms | 81,77 ms | -13,1% |
| p95 amostral | 174,20 ms | 163,77 ms | -6,0% |
| Pico `tracemalloc` (consulta "projeto") | 4,15 MiB | 2,86 MiB | -31,1% |

**Limitações:** medição sintética em Linux Python 3.13 com processos e volume diferentes do Pop!_OS do usuário; não é garantia de ganho no hardware dele. O p95 com 84 observações ainda apresenta incerteza, e a variabilidade de máquinas e processos pode superar parte do ganho. O script reutilizável em `scripts/benchmark_search.py` gera a base sintética automaticamente, sem tocar no banco do usuário; executar separadamente nas versões antes/depois para replicar.

## Segurança e continuidade

Não foi encontrado motivo confirmado para substituir FastAPI/SQLite/JS por frameworks ou banco pesado. Nenhuma alteração em contratos públicos, dados reais, `init_env`, credenciais, APIs pagas, portas externas ou StepFlow. Formato dos arquivos KHB1/Fernet preservado. Na restauração, ZIPs legados com conteúdo único `hub.db` continuam aceitos até 512 MiB descompactados; backups acima desse limite agora são recusados preventivamente, o que deve ser levado em conta antes de acumular bancos maiores. A restauração `os.link()` é intencionalmente direcionada a Pop!_OS/Linux e arquivos de mesmo filesystem. Não alegar segurança absoluta sem testes adicionais.

## Referências públicas

- Python `zipfile`: https://docs.python.org/3/library/zipfile.html — documentação de decompression bombs e leitura em fluxo.
- SQLite online backup: https://sqlite.org/backup.html — consistência de snapshots de bancos ativos.
- GitHub Actions e Node20: https://github.blog/changelog/2026-09-23-node-20-is-no-longer-available-in-github-actions/

## Prioridades posteriores

1. Repetir benchmarks no hardware real quando houver disponibilidade, com banco **fictício**, não o real.
2. Obter cobertura de branches de autenticação, migrações, agenda e aprovação, com ferramenta leve opcional.
3. Investigar modularização adicional somente com extração de responsabilidade bem delimitada e testes.
4. Revalidar exportação e restauração com dados volumosos e cancelamento de escrita.
5. Executar E2E Chrome/Firefox real contra backend, distinto de DOM simulado.
