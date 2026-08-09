# Data Model: Recuperação DAVE / gaps de gravação

**Feature**: `004-dave-decrypt-recovery`  
**Date**: 2026-08-08  
**Spec**: [spec.md](./spec.md)

## Overview

```text
Voice recv (py-cord) ──fail──► DaveRecovery.on_decrypt_failure
                 └──PCM OK──► Sink.write ──► DaveRecovery.on_decode_success

DaveRecovery ──threshold──► reconnect_voice_full ──► GapsLog + mid-session webhook
Session end ──► end webhook (+ gap_count) + Discord reply
```

---

## Entity: DaveRecoveryState (in-memory)

Estado por sessão ativa (não persistido).

| Field | Type | Description |
|-------|------|-------------|
| `failure_timestamps` | list[float] | Monotonic or wall times of consecutive decrypt failures |
| `cooldown_until` | float \| None | Earliest time a new auto-recovery may start |
| `recovery_in_progress` | bool | Blocks re-entrancy |
| `awaiting_validation` | bool | Connected; waiting for first PCM OK |
| `validation_deadline` | float \| None | Timeout for post-connect validation |
| `gap_started_at` | str \| None | ISO-Z when current gap opened |
| `gap_start_ms` | int \| None | ms since session.started_at |
| `attempts` | int | Reconnect attempts in current incident |
| `gaps_completed` | int | Count of closed gap records this session |

### Transitions

```text
idle --threshold--> recovering --connect--> awaiting_validation
                      |                         |
                      |                   PCM OK --> idle (+ cooldown)
                      |                   timeout --> recovering (next attempt)
                      max attempts --> compromised (voice left, session open)
compromised --manual encerrar--> (session end)
```

---

## Entity: RecordingGap (JSONL line)

Arquivo: `{RECORDINGS_DIR}/{session_id}/recording_gaps.jsonl`  
Schema: [contracts/recording-gaps.schema.json](./contracts/recording-gaps.schema.json)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Id da sessão |
| `started_at` | string (date-time) | yes | Início do gap (UTC) |
| `finished_at` | string (date-time) | yes | Fim do incidente (UTC) |
| `start_ms` | integer ≥ 0 | yes | Relativo a `session.started_at` |
| `end_ms` | integer ≥ 0 | yes | Relativo a `session.started_at` |
| `reason` | string | yes | Constante `dave_decrypt_failure` |
| `reconnect_attempts` | integer ≥ 0 | yes | Tentativas até fechar o gap |
| `success` | boolean | yes | `true` se validado com PCM OK |

### Validation

- Uma linha por incidente fechado (sucesso ou esgotamento).
- `end_ms >= start_ms`.
- Append-only; encoding UTF-8.

---

## Entity: MidSessionAlert

POST JSON para `CRONISTA_ALERT_WEBHOOK_URL`.  
Schema: [contracts/mid-session-alert.schema.json](./contracts/mid-session-alert.schema.json)

| Field | Type | Description |
|-------|------|-------------|
| `event` | enum | `dave_decrypt_detected` \| `dave_decrypt_recovered` \| `dave_decrypt_failed` |
| `session_id` | string | |
| `channel_id` | string | |
| `guild_id` | string | |
| `message` | string | Texto pronto para bridge Telegram |
| `gap_started_at` | string | ISO-Z |
| `gap_duration_s` | number \| omit | Presente em recovered/failed |
| `reconnect_attempts` | integer \| omit | |
| `success` | boolean \| omit | |

---

## Entity: SessionEndPayload (extension)

Campos **aditivos** no webhook n8n existente (`notify_session_ended`):

| Field | Type | Description |
|-------|------|-------------|
| `gap_count` | integer ≥ 0 | Número de linhas em `recording_gaps.jsonl` |
| `recording_gaps_path` | string \| omit | Path absoluto se `gap_count > 0` |

Contrato base permanece em `specs/002-python-pycord-migration/contracts/n8n-webhook.schema.json` (atualizar ou documentar extensão em [contracts/api.md](./contracts/api.md)).

---

## Runtime Config (new env)

| Env | Default | Field |
|-----|---------|-------|
| `CRONISTA_DAVE_FAILURE_THRESHOLD` | `5` | `dave_failure_threshold` |
| `CRONISTA_DAVE_FAILURE_WINDOW_S` | `10` | `dave_failure_window_s` |
| `CRONISTA_RECONNECT_MAX_ATTEMPTS` | `5` | `reconnect_max_attempts` |
| `CRONISTA_RECONNECT_BACKOFF_S` | `3` | `reconnect_backoff_s` |
| `CRONISTA_RECOVERY_COOLDOWN_S` | `60` | `recovery_cooldown_s` |
| `CRONISTA_RECONNECT_VALIDATE_TIMEOUT_S` | `30` | `reconnect_validate_timeout_s` |
| `CRONISTA_ALERT_WEBHOOK_URL` | unset | `alert_webhook_url` |

---

## Relationships

- **SessionData** 1 → 0..N **RecordingGap**
- **DaveRecoveryState** 1 → 0..1 gap aberto → fecha em **RecordingGap**
- **MidSessionAlert** emitido 1..3 vezes por incidente (detect / recover|fail)
