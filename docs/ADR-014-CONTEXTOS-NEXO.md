# ADR-014 — Projeções contextuais NEXO 14.0

## Motivo
O contexto do projeto fazia quatro requisições, incluindo a listagem inteira de eventos para filtrar no navegador. O cartão da oportunidade não expunha tarefas, notas e atividades vinculadas em uma visão.

## Decisão
Enriquecer o endpoint de projeto com notas e compromissos filtrados no SQLite; criar uma projeção de oportunidade autenticada. Ambos usam relações já existentes e retornam dados verdadeiros, sem gravar auditoria em GET nem fabricar vínculos.

## Limites
Não inferir compromisso de oportunidade a partir de compromisso de contato: o contato pode ter múltiplas oportunidades. Limitar notas, eventos e histórico; máximo inicial de 60 tarefas por oportunidade. Preservar CSRF, sessão, CSP, fonte única de verdade e esquemas 001–006.

## Fontes
SQLite EXPLAIN QUERY PLAN: https://www.sqlite.org/eqp.html
WAI disclosure pattern: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
