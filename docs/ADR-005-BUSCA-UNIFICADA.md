# ADR-005 — Busca local e navegação contextual (v11)

**Data:** 2026-11-11 · **Decisão:** adotar busca contextual autenticada sem índice duplicado nesta escala.

## Problema

Para encontrar um contato, oportunidade ou tarefa era necessário lembrar a seção certa. Os vínculos entre contato, oportunidade e tarefa já existem no SQLite, mas não eram pesquisáveis transversalmente. Usuário solicita fluxo operacional mais natural e menos navegação fragmentada.

## Alternativas

- **A — Pesquisa local em SQLite + normalização Unicode em Python (adotada):** zero migração, zero serviço novo, dados atuais permanecem única fonte de verdade. Busca contextual por título, empresa, pessoa, e-mail, projeto e próximo passo; suporta diferenças de acentos e maiúsculas.
- **B — SQLite FTS5:** boa opção se o volume crescer, mas requer sincronização de índice e migração, sem benefício demonstrado para os dados pessoais atuais; a busca exata por termo parcial exige decisão sobre tokenização. Referência: https://www.sqlite.org/fts5.html
- **C — Sistema externo Elasticsearch/Meilisearch:** não justificado pelo contexto local e custo operacional.

## Implementação

`GET /api/search?q=...` exige sessão e retorna apenas registros persistidos, limitados a 40 itens (até 8 por entidade). A consulta é somente leitura. A normalização usa NFKD para tolerar acentos, sem interpolação SQL externa. O algoritmo ordena coincidências exatas e por prefixo acima das coincidências de contexto.

O campo `kind` é limitado aos módulos conhecidos. A interface usa `safe()` em todo texto dinâmico, navega ao registro original, foca-o e permite abrir a pesquisa com `Ctrl+K`/`⌘K`. O diálogo é nativo, com controles de teclado e feedback para ausência de resultados.

Nenhum dado é enviado a provedores externos. Busca não é interpretação por IA. Nenhum índice externo nem duplicação de registros.

## Limites / gates

- Para volumes muito grandes, o custo de percorrer resultados pode aumentar: instrumentar e migrar para índice especializado somente com evidência de lentidão.
- A navegação ao registro é feita carregando as seções existentes. A abordagem pode precisar de paginação quando a quantidade por seção crescer; neste MVP a escala é local individual.
- Acessibilidade e responsividade foram verificadas por testes automatizados, mas teste humano com teclado e leitor de tela no Pop!_OS permanece pendente.
