# Contracts: Telegram DAVE mid-session alerts

**Feature**: `005-telegram-dave-alerts`

## Transport

| Item | Value |
|------|--------|
| Protocol | HTTPS Telegram Bot API |
| Method | `POST` |
| Path | `{api_base}/bot{token}/sendMessage` |
| Content-Type | `application/json` |
| Retries | 3 (backoff curto) |
| Schema body | [telegram-sendmessage.schema.json](./telegram-sendmessage.schema.json) |

`api_base` default: `https://api.telegram.org`

---

## Message texts (normative)

| Event | When | `text` |
|-------|------|--------|
| Detected | Threshold hit; recovery starting (parallel) | `⚠️ Cronista: falha de decriptação DAVE detectada no canal {channel}, tentando reconectar...` |
| Recovered | First PCM OK after reconnect | `✅ Reconexão bem-sucedida, gravação retomada após {duração_do_gap}` |
| Failed | Max reconnect attempts exhausted | `🔴 Falha ao reconectar após {N} tentativas — gravação da sessão comprometida a partir de {horário}` |

Placeholders: ver [spec.md](../spec.md) e [data-model.md](../data-model.md).

---

## Configuração

| Variable | Role |
|----------|------|
| `CRONISTA_TELEGRAM_BOT_TOKEN` | Token do bot |
| `CRONISTA_TELEGRAM_CHAT_ID` | Destino |
| `CRONISTA_TELEGRAM_API_BASE` | Override opcional da base URL |

Se Token ou Chat ID ausentes: **não** chamar a API; log de omissão; recovery/gaps seguem.

---

## Removido

| Contrato 004 | Status |
|--------------|--------|
| Mid-session webhook `CRONISTA_ALERT_WEBHOOK_URL` + [mid-session-alert.schema.json](../../004-dave-decrypt-recovery/contracts/mid-session-alert.schema.json) | **Não** é mais o transporte de produção |

---

## Inalterado

- Session-end n8n webhook (`N8N_WEBHOOK_URL`) — [002 n8n-webhook.schema.json](../../002-python-pycord-migration/contracts/n8n-webhook.schema.json) + campos aditivos `gap_count` / `recording_gaps_path` de 004
- `recording_gaps.jsonl`
- Comandos `!cronista` e layout de gravação
