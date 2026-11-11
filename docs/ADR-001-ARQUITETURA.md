# ADR-001 — Piloto enxuto do Kelwin Hub, sem revogar Java/Spring

**Data:** 11/11/2026 · **Status:** decisão experimental e reversível, não substitui documento canônico

## Problema

O documento canônico v0.2 escolheu como direção Java 25 + Spring/Spring Modulith, PostgreSQL, React/TypeScript e PWA. A missão mais recente acrescenta n8n, EspoCRM, um Atlas com 240 automações, uso individual e computador de aproximadamente 8 GiB RAM. Precisamos validar rapidamente um fluxo útil sem confundir planejamento com implementação e sem introduzir serviços pesados por padrão.

## Alternativas consideradas

- **A. Hub próprio Java/Spring/PostgreSQL + n8n opcional:** preserva a direção canônica; boa separação de domínio; necessita JDK 25, toolchain e banco. Melhor candidata a núcleo definitivo quando disponível e medida no computador-alvo.
- **B. Hub + EspoCRM + n8n:** aproveita CRM e integrações, mas cria duas ou três interfaces/serviços, mais persistências e necessidade de sincronização; custo operacional mais alto em 8 GiB.
- **C. Piloto enxuto e modular (implementado):** Python FastAPI, SQLite WAL, JavaScript/CSS local, jobs internos; n8n como adição opcional. Não reivindica equivalência arquitetural a Java/Modulith. Entrega prova de valor sem alterar repositórios existentes.

### Matriz de decisão *heurística*, não benchmark comparativo

Escala 1–5 (5 é melhor). Pesos: recursos 20%, manutenção 20%, UX 15%, portabilidade 15%, confiabilidade/segurança 15%, reutilização 10%, aprendizado alinhado ao usuário 5%.

| Critério | Peso | A | B | C |
|---|---:|---:|---:|---:|
| Recursos/memória esperados | 20% | 4 | 2 | 5 |
| Manutenção esperada | 20% | 3 | 2 | 5 |
| UX potencial | 15% | 5 | 4 | 4 |
| Portabilidade | 15% | 4 | 3 | 5 |
| Confiabilidade e segurança potencial | 15% | 4 | 3 | 4 |
| Reuso de trabalho existente | 10% | 4 | 5 | 3 |
| Aprendizado alinhado ao Java | 5% | 5 | 4 | 3 |
| **Soma ponderada (/5)** | **100%** | **4,00** | **3,00** | **4,40** |

Estas notas são estimativas, **não medidas empíricas das três arquiteturas**. A alternativa C ganha apenas como **piloto de validação**. A arquitetura definitiva continua pendente de evidências no Pop!_OS e eventual revisão do documento canônico.

## Implementação comprovada nesta execução

FastAPI, SQLite, autenticação local, web UI, CRUD parcial dos módulos centrais, eventos locais, automação determinística A10-02 e backup cifrado. A primeira jornada foi testada com TestClient e solicitações HTTP reais ao servidor local. Sem Docker real, n8n real, OAuth ou EspoCRM.

## Contratos e limites

- A fonte de verdade de projetos/tarefas/contatos/oportunidades **do piloto** é SQLite. Em uma migração, transições devem preservar IDs e auditoria ou registrar mapa explícito.
- Agendador interno somente cria alertas; sua tabela não é publicada no n8n.
- Arquivo de workflow n8n é uma **adaptação preparada, não homologada**.
- EspoCRM é opcional e **não foi instalado** nesta entrega.
- Dados Google/GitHub permanecem nas respectivas fontes; nada é importado neste piloto.
- StepFlow é produto independente e não foi modificado.

## Gatilho de revisão

Executar no Pop!_OS e medir RAM, CPU, tempo de inicialização, responsividade e facilidade de manutenção. Se Java/Spring for confirmado como direção de produto e houver benefício justificado, portar domínio e contratos do piloto, mantendo exportação/migração e evitando duas fontes de verdade paralelas.
