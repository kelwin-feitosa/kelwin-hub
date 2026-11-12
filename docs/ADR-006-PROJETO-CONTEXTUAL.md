# ADR-006 — Detalhe de projeto expansível em contexto

**Data:** 2026-11-11 · **Decisão:** acrescentar projeção read-only e expansão acessível; não migrar tabelas.

## Problema e alternativas

A tela de projetos só mostrava nome, área e status. Para retomar trabalho era necessário acessar tarefas, encontrar os registros e lembrar seu vínculo. Alternativas: abrir uma seção nova (mais cliques), criar editor/kanban completo (alto custo) ou **expandir os dados relacionados no próprio projeto** (escolhida para piloto). Uma página dedicada por projeto pode ser avaliada quando houver documentos, dependências e mais dados.

## Implementação

`GET /api/projects/{id}/context` exige autenticação, consulta tarefas pertencentes ao projeto e fornece contadores reais de abertas, bloqueadas e concluídas, próxima tarefa aberta e atividades auditadas. Não inventa uma porcentagem de progresso e não encerra o projeto automaticamente.

No frontend, o botão **Contexto** expande o detalhe sem sair da seção. É possível criar tarefa já vinculada ao projeto, concluir tarefas e retornar ao contexto. Navegação pela pesquisa abre e foca o projeto correto. Tudo utiliza endpoints existentes para escrita. Sem novas dependências ou migrações.

## Validação

Testes incluem ausência de sessão, projeto inexistente, separação entre dois projetos, contadores, atualização de tarefa e imutabilidade do status do projeto. Browser real e revisão de acessibilidade com tecnologia assistiva ainda são validações externas pendentes.
