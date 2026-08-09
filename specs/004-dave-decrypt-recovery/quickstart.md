# Quickstart: Recuperação DAVE / gaps

**Feature**: `004-dave-decrypt-recovery`  
**Contracts**: [contracts/api.md](./contracts/api.md) · **Data model**: [data-model.md](./data-model.md)

Validação pós-implementação (Discord ao vivo + receptor de webhook).

## Prerequisites

- Cronista rodando com venv isolado e token válido
- Canal de voz de teste (2+ humanos recomendado)
- `CRONISTA_ALERT_WEBHOOK_URL` apontando para receptor de teste (webhook.site, n8n, ou monitor Telegram)
- Env DAVE com defaults ou explícitos (ver data-model)

```bash
cd /opt/apps/cronista   # ou app/ local
# garantir CRONISTA_ALERT_WEBHOOK_URL no .env
systemctl --user restart cronista   # ou processo local
```

## Scenario 1 — Happy path (detect → recover)

1. `!cronista entrar` no canal de teste; confirmar gravação com fala.
2. Forçar perda de captura: no host, desconectar o voice client de forma controlada **ou** usar o hook de teste documentado na implementação (injetar N falhas consecutivas).
   - Alternativa aceita pela spec: `voice_client.disconnect()` durante gravação e observar se o orchestrator trata como falha de decriptação/reconnect conforme o gancho R1.
3. Observar:
   - Webhook `dave_decrypt_detected`
   - Reconnect completo (bot some e volta ao canal)
   - Após fala humana: webhook `dave_decrypt_recovered`
   - Linha em `{RECORDINGS_DIR}/{session_id}/recording_gaps.jsonl` com `success: true`
4. Confirmar novas linhas em `speaking_log.jsonl` após a recuperação.

**Esperado**: SC-001–SC-004, SC-007 (arquivos pré-gap intactos).

## Scenario 2 — Esgotar tentativas

1. Simular reconnect impossível (ex.: remover permissão de Connect temporariamente, ou mock de connect falhando em teste automatizado).
2. Atingir limiar de falhas.
3. Observar até `CRONISTA_RECONNECT_MAX_ATTEMPTS`.

**Esperado**: webhook `dave_decrypt_failed`; bot **fora** do voz; sessão ainda “ativa” no status; gap com `success: false`; **sem** auto-encerrar.

## Scenario 3 — Cooldown

1. Completar Scenario 1.
2. Dentro de 60s, injetar novamente o limiar de falhas.

**Esperado**: sem novo ciclo automático até expirar o cooldown (falhas apenas em log).

## Scenario 4 — Gaps no encerramento

1. Sessão com ≥1 gap.
2. `!cronista encerrar`.

**Esperado**: reply Discord menciona contagem de gaps; payload n8n inclui `gap_count` (+ path se >0).

## Scenario 5 — Sem alert URL

1. Remover `CRONISTA_ALERT_WEBHOOK_URL`.
2. Disparar recovery.

**Esperado**: gaps e reconnect funcionam; log indica alerta omitido.

## Checklist

- [ ] Scenario 1 — detect + recover + gap success + speaking_log retoma (manual Discord)
- [ ] Scenario 2 — failed + voice left + session open (manual / permissão)
- [ ] Scenario 3 — cooldown respeitado (manual ou unit)
- [ ] Scenario 4 — encerrar com gap_count (manual)
- [ ] Scenario 5 — sem URL de alerta (unit + opcional manual)
- [x] Unit tests `pytest` em `app/tests/unit/` (recovery, gaps, webhook) — 24 passed
