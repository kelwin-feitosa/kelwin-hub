# Estudo de hospedagem e disponibilidade — 11/11/2026

**Objetivo:** funcionar gratuitamente no PC principal; hospedar fora somente após medir o uso. Custo de hospedagem R$ 0 **não significa energia, internet e armazenamento gratuitos**.

| Cenário | Vantagem | Risco / limitação | Decisão |
|---|---|---|---|
| **PC Pop!_OS local (~4 núcleos, ~8 GiB)** | Sem contratação, privacidade, debug fácil | Suspensão/desligamento interrompem jobs; compete com IDE/Docker | **Primeiro ambiente** |
| **Notebook antigo recuperado** | Pode atender 24/7 sem assinatura | Estado desconhecido; fonte, SSD, bateria, temperatura, consumo, reparos | **Preferido para piloto permanente se custo compensar** |
| Servidor doméstico dedicado | Portabilidade, disponibilidade | Compra, energia e manutenção; sem justificativa antes do piloto | Adiar |
| **Oracle OCI Always Free** | Documentação anuncia até 2 OCPUs ARM + 12 GiB RAM, conforme créditos Always Free em horas de uso | Capacidade da região, compatibilidade ARM, conta, rede, instância ociosa recuperável | Alternativa interessante, não garantida |
| **Google Cloud Free Tier** | Uma e2-micro elegível, disco limitado, teste sem tarifa dentro da cota | Máquina restrita, regiões dos EUA, tráfego e excedentes; não supor RAM suficiente para stack completa | Apenas serviços pequenos |
| Híbrido | PC UI + notebook jobs | Dois pontos de falha e sincronização mais complexa | Adiar |

### Fontes verificadas

- Oracle: <https://docs.oracle.com/pt-br/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm> — benefícios, 1.500 OCPU-h + 9.000 GB-h por mês, capacidade insuficiente e recuperação de instância ociosa.
- Google: <https://docs.cloud.google.com/free/docs/free-cloud-features?hl=pt-br> — e2-micro em regiões específicas, disco e transferência gratuitos limitados.
- Tailscale: <https://tailscale.com/pricing> — uso **pessoal não comercial** gratuito; verificar enquadramento antes de acesso relacionado a atividade profissional.

### Diagnóstico do notebook antigo (não foi fornecido)

Antes de gastar com reparo, verificar: marca/modelo, processador e arquitetura, RAM total e máxima, SSD/HDD, saúde do disco (SMART), temperaturas, fonte, bateria inchada ou comprometida (não utilizar), consumo em repouso e sob carga, Ethernet/Wi-Fi, suspensão, ventilação, BIOS após queda de energia e ruído. Testar inicialmente com Debian/Ubuntu Server sem interface gráfica; estimar substituição de SSD e RAM somente após medir.

### Energia e custo

Fórmula: `kWh por mês ≈ Watts médios × 24 × 30 / 1000`. Exemplo hipotético de 12 W médios: **8,64 kWh/mês**. Para estimar reais, multiplicar pela tarifa final do usuário com tributos, bandeiras e encargos. Não há medições nem tarifa reais fornecidas; portanto não foi calculado custo em R$.

### Acesso remoto

Preferir uma VPN privada, com autenticação forte (WireGuard ou Tailscale), e HTTPS quando possível. **Não publicar** portas de PostgreSQL, n8n ou serviço administrativo. O n8n não precisa de um webhook público para os jobs locais; integrações Gmail/Calendar podem usar polling autorizado respeitando cotas e limites. Mesmo em VPN, revisar autenticação, backup e superfície de ataque.

### Plano de migração

1. Medir 7 dias de uso local e necessidade real de 24/7.
2. Testar backup cifrado/restauração, quedas de energia e reinício.
3. Avaliar notebook antigo e custo total versus nuvem gratuita.
4. Migrar banco e `.env` com canal seguro, nunca publicar credenciais em repositório.
5. Testar TLS, rede, permissões e automações agendadas após migração.
6. Manter rollback sem sincronização bidirecional improvisada.
