# ADR-013 — Navegação orientada por contexto e catálogo de ferramentas

**Estado:** adotada tecnicamente (homologação humana pendente). **Missão:** 13.6 — ÓRBITA.

## Problema confirmado

Antes, todas as oito áreas ocupavam permanentemente a barra lateral. Em telas estreitas o menu se tornava uma faixa horizontal rolável. Novas funcionalidades exigiriam mais opções permanentes ou menus arbitrários. A busca global já existia para registros, mas não descobria áreas e ações.

## Alternativas comparadas

| Alternativa | Descoberta | Escalabilidade | Custo de mudança | Problema principal |
|---|---|---|---|---|
| Barra lateral agrupada | Boa para oito módulos | Decai com expansão | Baixo | Continua crescendo |
| Paleta de comandos exclusiva | Boa para especialistas | Alta | Médio | Difícil de descobrir por toque |
| Agrupamento por intenções em menu único | Médio | Médio | Médio | Termos abstratos e etapas extras |
| **4 destinos + catálogo + iniciador** | **Acesso persistente + diretório explícito** | **Aumentar categorias sem multiplicar destinos** | **Baixo** | Uma etapa extra para seções não fixadas |

## Decisão

Manter permanentemente **Mesa, Projetos, Agenda e Explorar**. A página Explorar é um catálogo por finalidade (Começar, Trabalhar, Acompanhar e Planejar), com todas as áreas existentes e ações contextualizadas. A pesquisa global existente passa a combinar **registros privados** (mesma API `/api/search`) com **destinos e ações locais**. O botão visível **Novo** abre a mesma paleta filtrada por criação. Teclado e clique são opcionais, nenhum recurso exige atalhos para funcionar.

Em mobile, usar um dock inferior compacto de quatro áreas, com safe-area e sem rolagem horizontal. Exportação e saída da sessão permanecem descobríveis na página Explorar, além de seus controles existentes no desktop. O foco após a navegação e os estados ativos devem ser coerentes. O histórico de navegação usa apenas o identificador público do módulo, não dados de registros.

## Segurança e integridade

- O catálogo é uma lista estática de comandos autorizados. Nenhum código arbitrário é executado a partir de consultas do usuário.
- Ações de criação invocam o código existente, respeitando autenticação e CSRF; a paleta não oferece ações destrutivas.
- Nenhuma nova tabela ou migração. Todas as rotas e funcionalidades existentes permanecem.
- Sem bibliotecas frontend, chamadas de rede ou serviços pagos novos.
- A CSS própria da ORBITA sobrescreve apenas a casca de navegação e o diretório; a limpeza completa de regras antigas requer uma auditoria visual independente para evitar regressões.

## Validação e limites

Os testes automáticos verificam contratos de navegação, acessibilidade estrutural, oito áreas descobríveis, seis ações rápidas e saída por mouse/teclado. Os resultados não substituem teste real de navegador com backend nem avaliação humana de usabilidade. Validar zoom, viewports pequenas e tema claro/escuro antes de classificação como versão estável.

## Referências consultadas

- NN/g, Progressive Disclosure — https://www.nngroup.com/articles/progressive-disclosure/
- Atlassian Design, Navigation system — https://atlassian.design/components/navigation-system/migration-guide
- W3C, WCAG 2.2 — https://www.w3.org/TR/WCAG22/
- OWASP ASVS 5.0 — https://asvs.owasp.org/
