# ADR-012 — Disponibilidade privada, sem agendamento público

**Missão 13.0 / 12/11/2026**

## Decisão

Adicionar faixas semanais opcionais no SQLite (migração `006_availability_windows.sql`). Não há disponibilidade presumida: se o usuário não cadastrou faixas, nenhum slot é oferecido. O módulo utiliza fuso IANA `America/Sao_Paulo` via `zoneinfo`, janelas locais, duração e passo configuráveis e buffer opcional.

- `GET /api/availability/windows`: listar faixas (autenticado).
- `POST /api/availability/windows`: inserir faixa semanal, com limite de 8 faixas/dia e recusa de sobreposição (sessão+CSRF).
- `DELETE /api/availability/windows/{id}`: remover faixa (sessão+CSRF).
- `GET /api/availability/slots?day=AAAA-MM-DD&duration=30&step=15&buffer=0`: calcula no máximo 100 slots locais livres, ignorando eventos propostos/cancelados e bloqueando **confirmados**. Retorna timestamps em UTC e referências em fuso local.
- Interface da Agenda apresenta janelas, slots e ação para **criar um evento local confirmado**; essa ação chama `/api/events`, que revalida o conflito em transação `BEGIN IMMEDIATE` já existente. Preview nunca garante reserva futura.

## Limites conhecidos

1. **Não há página pública**, URL de reserva, convites, e-mails, HTTPS, integração Google Calendar ou Outlook, nem sincronização externa.
2. A disponibilidade aplica-se apenas à agenda **registrada no Hub**, podendo conflitar com agendas externas ainda não integradas.
3. Janelas diárias não atravessam meia-noite; períodos noturnos serão modelados como duas faixas.
4. Alguns casos de horário ambíguo em mudanças de fuso/DST podem requerer ajuste posterior; horas locais inexistentes são descartadas por roundtrip, sem prometer tratamento perfeito de todos os fusos.
5. O buffer controla apenas o preview; a rota administrativa `/api/events` não impõe buffers, mas verifica conflito real com eventos confirmados.
6. Ainda não houve homologação visual pelo usuário no Pop!_OS; testes de API são distintos de testes E2E de navegador.

## Próximos passos

Considerar perfis de reunião, exceções por data, antecedência mínima e domínio público isolado com segurança após validação das necessidades. Sempre manter interface administrativa privada.
