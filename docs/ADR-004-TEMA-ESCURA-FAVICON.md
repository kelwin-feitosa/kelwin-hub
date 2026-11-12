# ADR-004 — Tema escuro neutro, tokens sem duplicidade e favicon local

**Data:** 2026-11-11 · **Estado:** implementação verificada localmente; validação estética no Pop!_OS depende do usuário.

## Motivação

O usuário rejeitou os tons verdes nos fundos e controles do tema escuro. `app.css` continha tokens das versões 7 e 10 sobrepostos, com correções específicas de tema espalhadas; o navegador também solicitava `/favicon.ico` e recebia 404.

## Alternativas examinadas

- **A — Ardósia/grafite + acento azul suave (escolhida):** identidade discreta, contraste forte e sem tingimento verde nos fundos.
- **B — Cinza neutro + âmbar:** contraste agradável, mas numerosos indicadores de estado poderiam competir com o acento.
- **C — Escuro levemente quente:** alternativa futura a testar com feedback do usuário.

## Mudanças

- Tokens de tema definidos uma única vez no topo de `app.css`, com cores semânticas para conteúdo, borda, ações, estados e foco.
- Acabam as regras tardias de cores fixas para botões, links e destaques da Mesa. Verde permanece apenas como uma opção semântica de **sucesso**, não como fundo estrutural.
- `prefers-color-scheme` usado quando não existe escolha salva pelo usuário; o seletor continua persistindo a preferência local.
- `hub/static/favicon.svg` é servido em `/favicon.ico` como `image/svg+xml` no endereço local, com `<link rel="icon">` no HTML. Nada de fontes ou CDNs.
- Testes de regressão verificam respostas HTTP, tokens e respeito à preferência do sistema; acesso root sem autenticação necessário para ícone e página de login.

## Critérios e limitações

- Os contrastes foram verificados por cálculo de luminância das cores-base, **não** por auditoria de cada pixel ou de todas as combinações de estado. Referência: [WCAG 2.2 1.4.3](https://www.w3.org/TR/WCAG22/#contrast-minimum).
- Dark mode renderizado em navegadores diferentes e feedback humano sobre a nova paleta ainda precisam ser confirmados no Pop!_OS.
- Nenhuma migração de banco, alteração de credenciais ou custo recorrente.
