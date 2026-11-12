# ADR-008 — Notas contextuais e histórico factual

**Data:** 2026-11-11 · **Missão:** Kelwin Hub 12.0 · **Decisão:** notas nativas leves e reaproveitamento do audit existente.

## Contexto e alternativas

Notas isoladas em outra ferramenta perderiam vínculo com projetos e oportunidades. Foram consideradas (a) conteúdo livre dentro das descrições existentes, (b) notas em uma tabela única com FKs opcionais, (c) documentos genéricos polimórficos e (d) aplicativo externo. Escolhemos **(b)** para permitir pesquisa, edição, timestamps próprios e referências seguras, sem editor rico ou serviço adicional.

O histórico de ações já é registrado na tabela `audit`. Criar um segundo event store seria duplicação. A consulta contextual de `audit` reúne eventos do próprio projeto, das tarefas e notas atualmente associadas, com paginação e ordenação estável. Os eventos anteriores permanecem fatos do tipo ação registrada; **não** inventamos detalhes históricos ou mudanças que não foram capturadas. A associação de uma tarefa é imutável no piloto; notas possuem vínculos de criação imutáveis na primeira versão. Não se trata de sistema de event sourcing.

## Implementação

- Migração `002_notes_context.sql` aditiva (FK para projetos, contatos e oportunidades, índices de pesquisa contextual, integridade textual). Atualização de `Store.MIGRATION_NAMES` para mapear migrações pelo nome real; `user_version=2` com transação e rollback automático ao falhar.
- `POST /api/notes`, `GET /api/notes` com filtros validados, `PATCH /api/notes/{id}` para título/corpo, `GET /api/activity` com `kind`/`ident` whitelisted. Sessão e CSRF de escrita existentes; corpo limitado a 12 mil caracteres; campos SQL dinâmicos são chaves internas fixas, parâmetros para valores.
- Uma nota pode ter vínculos opcionais múltiplos, todos validados dentro da transação de criação. A primeira versão não oferece alterar vínculos nem exclusão; evita perda acidental.
- Busca unificada pesquisa também conteúdo e contexto das notas. Interface de notas simples com `<textarea>`, valores escapados, e notas/atividades exibidas dentro do contexto do projeto. Exportação JSON inclui notas; versão JSON externa continua 1 porque não existe importador público e os campos anteriores foram preservados.
- Nenhum envio externo nem custo recorrente.

## Limites

- Histórico textual reduzido a `kind`, `action`, horário e ID por ausência de snapshots; eventos não comprovados não aparecem.
- Busca inicial em memória, conforme ADR-005; limitar/paginar antes de bases muito grandes.
- O usuário ainda precisará avaliar a experiência no Pop!_OS. Testes automatizados com dados fictícios não substituem aprovação visual.
