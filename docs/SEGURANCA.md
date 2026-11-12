# Segurança, privacidade e limitações

## Controles presentes no piloto

- Acesso padrão apenas em loopback `127.0.0.1` (script nativo e porta publicada via Docker).
- Login de usuário único, senha PBKDF2-SHA256 com salt e alto custo; sessão assinada com expiração em 12 horas.
- Cookie HttpOnly + SameSite Strict; CSRF por segredo derivado da sessão e verificação de Origin quando presente.
- Política CSP sem scripts remotos, X-Frame-Options DENY, Referrer-Policy no-referrer.
- Query SQL parametrizada, chaves estrangeiras, SQLite WAL, validação de tipos e valores.
- Senhas e tokens não ficam no banco de aplicação nem no GitHub; `.env` modo 0600.
- Endpoint interno opcional com token dedicado separado da sessão web.
- Histórico de eventos sem corpo das mensagens ou credenciais.
- Backups com snapshot SQLite consistente, compressão e cifragem autenticada Fernet, com KDF PBKDF2-HMAC-SHA256.
- Nenhum envio automático a terceiros ou integração com conta real.

## Limites que impedem implantação pública

1. A aplicação não está auditada profissionalmente. Login de usuário único **não é** suporte multiusuário.
2. A implementação guarda dados pessoais em banco **sem criptografia por campo**; proteja o disco, o usuário Linux e o acesso físico. A senha de backup é independente.
3. Não há TLS no acesso HTTP local; antes de VPN, reverse proxy ou nuvem revisar toda a superfície de ataque e o cookie `Secure`.
4. Falta proteção avançada contra força bruta distribuída, telemetria de intrusão, rotação de segredos, rate limit persistente e autorização granular.
5. Não há autorização para ingestão automática de Gmail, Drive, WhatsApp nem dados de instituições/clientes.
6. Não publicar APIs, n8n, banco ou UI diretamente na internet. Seguir princípio de menor privilégio e revisar LGPD ao incluir dados de terceiros.
7. Backups precisam ficar em outro dispositivo e passar por testes de restauração regulares. Perder a senha do backup impede recuperar os dados cifrados.
8. Agendamento local não fornece disponibilidade 24/7. Interrupções devem ser revisadas após reinício.
9. Templates n8n são experimentais; credenciais devem ser inseridas na interface do n8n, não no JSON.

## Revisão antes de dados reais

Executar um threat model mínimo, validar a imagem Docker real, testar backup/restore em máquina isolada, conferir permissões do volume, registrar versões, validar importação do n8n, implementar atualização segura e definir política de retenção. Nenhuma configuração de rede externa foi aplicada nesta entrega.


### FORJA 13.5 - Restricao de Host

O backend rejeita Host inesperado (400) via TrustedHostMiddleware. Sao aceitos 127.0.0.1, localhost, hub (Docker Compose/n8n opcional) e testserver (testes). Se no futuro houver VPN, dominio proprio ou reverse proxy, esta lista precisa de revisao explicita e medidas adicionais de HTTPS/rede; nao publicar o Hub administrativo apenas para suportar um host externo. Nenhum listener foi alterado.
