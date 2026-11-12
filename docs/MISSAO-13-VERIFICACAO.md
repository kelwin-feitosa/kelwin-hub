# Missão 13.0 — verificação técnica

## Entrega

Motor de revisão de reunião sem dependência de API: busca contextual com offsets, pacote de análise, contrato JSON estrito, persistência de análises e sugestões, revisão humana, criação transacional de tarefa e exclusão explícita de transcrições.

## Contratos

- `GET /api/meeting-review/transcripts/{id}/package`
- `GET /api/meeting-review/transcripts/{id}/analyses`
- `POST /api/meeting-review/transcripts/{id}/analyses`
- `POST /api/meeting-review/items/{id}/convert`
- `POST /api/meeting-review/items/{id}/dismiss`
- `DELETE /api/meeting-review/transcripts/{id}`
- `GET /api/meeting-review/search?q=`

Todos exigem sessão; métodos de escrita usam CSRF do Hub. Respostas privadas nunca devem ser colocadas no cache.

## Evidências e limites

Registrar aqui resultados efetivos de testes locais, GitHub Actions e possibilidade de navegação real. Teste de unidade/HTTP não implica acurácia de extração de IA, e o pacote não envia dados automaticamente.
