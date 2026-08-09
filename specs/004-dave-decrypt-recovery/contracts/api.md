# Contracts: DAVE decrypt recovery

**Feature**: `004-dave-decrypt-recovery`

## Artifacts

| Artifact | Schema / doc |
|----------|----------------|
| `recording_gaps.jsonl` | [recording-gaps.schema.json](./recording-gaps.schema.json) |
| Mid-session alert webhook | [mid-session-alert.schema.json](./mid-session-alert.schema.json) |
| Session-end n8n webhook (base) | [`specs/002-python-pycord-migration/contracts/n8n-webhook.schema.json`](../../002-python-pycord-migration/contracts/n8n-webhook.schema.json) |

---

## Mid-session alert webhook

**URL**: `CRONISTA_ALERT_WEBHOOK_URL` (optional)  
**Method**: `POST`  
**Content-Type**: `application/json`  
**Retries**: 3 (same style as session-end webhook)

### Events

| `event` | When | Typical `message` |
|---------|------|-------------------|
| `dave_decrypt_detected` | Threshold hit; recovery starting | `⚠️ Cronista: falha de decriptação DAVE detectada no canal {channel}, tentando reconectar...` |
| `dave_decrypt_recovered` | First PCM OK after reconnect | `✅ Reconexão bem-sucedida, gravação retomada após {duration}` |
| `dave_decrypt_failed` | Max attempts exhausted | `🔴 Falha ao reconectar após {N} tentativas — gravação da sessão comprometida a partir de {time}` |

If URL unset: log warning; recovery and gap logging continue.

---

## Session-end webhook (additive fields)

Além do payload atual, o Cronista SHOULD incluir:

| Field | Type | When |
|-------|------|------|
| `gap_count` | integer ≥ 0 | always |
| `recording_gaps_path` | string | when `gap_count > 0` |

Consumidores antigos que ignoram campos extras permanecem válidos.

---

## Discord operator UX

| Command | Change |
|---------|--------|
| `!cronista encerrar` | Reply includes gap count when `gap_count > 0` |
| `!cronista status` | Optional: mention recovery/compromised state and gap count if useful |

---

## Environment

See [data-model.md](../data-model.md) Runtime Config table (`CRONISTA_DAVE_*`, `CRONISTA_RECONNECT_*`, `CRONISTA_RECOVERY_COOLDOWN_S`, `CRONISTA_RECONNECT_VALIDATE_TIMEOUT_S`, `CRONISTA_ALERT_WEBHOOK_URL`).
