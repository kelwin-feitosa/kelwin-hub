# ADR-010 — Importação local e revisão de transcrições

**Missão 12.0 | Data: 11/11/2026**

## Decisão

Importação **opt-in** de transcrições textuais TXT/SRT/VTT existentes e autorizadas, vinculadas a um evento local. Não há bot, captura de microfone, gravação, API paga, análise de IA ou integração automática externa.

- Migração `004_transcripts.sql` cria `meeting_transcripts` com FK para evento, formato, nome original informado, corpo textual imutável e timestamp. Nada é apagado das versões 1–3.
- `POST /api/events/{id}/transcripts` exige sessão, CSRF, tipo permitido e limite de 200 KB UTF-8. API recebe conteúdo textual, não arquivo físico em caminho escolhido pelo cliente; upload no navegador usa `File.text()` e transmite texto pelo endpoint autorizado.
- `GET /api/events/{id}/transcripts` retorna apenas metadata + prefixo curto, sem corpo completo; `GET /api/transcripts/{id}` retorna o texto e segmentos explícitos com marcações de tempo. Nenhuma decisão ou responsável é inferido automaticamente.
- O conteúdo da transcrição é **dado não confiável** e HTML escapado na UI. Não são executadas instruções da transcrição. CLI de backup criptografado cobre a tabela por snapshot SQLite; exportação JSON inclui o texto privado e exige cuidado redobrado.
- Usuário deve obter consentimento legal para armazenar conteúdo de reuniões. Sem gerenciamento avançado de retenção ou exclusão nesta versão; não importar material sensível sem necessidade.

## Alternativas rejeitadas

- Bot que entra em conferências: infraestrutura e privacidade desnecessárias agora.
- Análise semântica por regex: risco de atribuir decisões falsas.
- Uso automático de API da OpenAI: credenciais, privacidade e custo não autorizados.
- Armazenar arquivos arbitrários em disco: complexidade, travessia de diretórios, gestão de permissões e backup adicional.

**Próximas etapas:** avaliação de retenção, seleção de trechos com origem, confirmação humana de ações; adaptador de provedor IA opcional só após autorização e definição de orçamento. Browser real em ambiente de execução atual bloqueia localhost, logo validação estética/fluxo visual ainda depende de PC do usuário.
