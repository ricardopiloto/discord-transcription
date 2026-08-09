# Data Model: Telegram DAVE alerts

**Feature**: `005-telegram-dave-alerts`

## Entities

### TelegramCredentials (runtime config)

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `bot_token` | string \| null | `CRONISTA_TELEGRAM_BOT_TOKEN` | Obrigatório para envio; nunca logar |
| `chat_id` | string \| null | `CRONISTA_TELEGRAM_CHAT_ID` | String (aceita IDs negativos de grupo) |
| `api_base` | string | `CRONISTA_TELEGRAM_API_BASE` | Default `https://api.telegram.org`; sem `/` final |

**Validation**:
- Envio só se `bot_token` e `chat_id` não-vazios
- `api_base` vazio → default oficial

### DaveAlertMessage

Mensagem textual pronta para `sendMessage.text`.

| Field | Type | Notes |
|-------|------|-------|
| `event` | enum | `dave_decrypt_detected` \| `dave_decrypt_recovered` \| `dave_decrypt_failed` |
| `text` | string | Resultado dos Message Templates da spec |
| `channel` | string | Nome do canal (fallback id) |
| `gap_duration_s` | float \| null | Só recovered — usado para formatar duração |
| `reconnect_attempts` | int \| null | Só failed |
| `gap_started_at` | string | ISO-8601 UTC — usado em failed como `{horário}` |

### SendResult

| Field | Type | Notes |
|-------|------|-------|
| `ok` | bool | `true` se Bot API aceitou |
| `omitted` | bool | `true` se credenciais ausentes |
| `attempts` | int | 1–3 |

## Relationships

```text
SessionManager._run_dave_recovery
  → build DaveAlertMessage (detected | recovered | failed)
  → telegram_alert.send (async; detected = create_task)
       → TelegramCredentials from Config
       → Bot API sendMessage
```

## Runtime Config (env)

| Variable | Default | Required |
|----------|---------|----------|
| `CRONISTA_TELEGRAM_BOT_TOKEN` | (unset) | para envio |
| `CRONISTA_TELEGRAM_CHAT_ID` | (unset) | para envio |
| `CRONISTA_TELEGRAM_API_BASE` | `https://api.telegram.org` | não |

**Removed / deprecated**:
| Variable | Disposition |
|----------|-------------|
| `CRONISTA_ALERT_WEBHOOK_URL` | Remover de config, `.env.example`, README |

## Message formatting rules

| Placeholder | Rule |
|-------------|------|
| `{channel}` | `channel_name` or `channel_id` |
| `{duração_do_gap}` | `<60s` → `{n}s`; else `{m}m {s}s` |
| `{N}` | integer attempts |
| `{horário}` | ISO-8601 UTC (`…Z`) |

Exact strings: see [spec.md Message Templates](./spec.md#message-templates-mandatory).

## Out of model scope

- Persistência de histórico de alertas
- Múltiplos chat IDs
- Payload JSON mid-session 004 como transporte
