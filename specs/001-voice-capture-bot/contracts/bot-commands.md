# Contract: Bot Commands

**Feature**: 001-voice-capture-bot  
**Interface**: Discord text messages (prefix commands)

## General Rules

- **Prefix**: `!cronista` (case-insensitive matching on command keyword)
- **Guild-only**: Commands ignored in DMs
- **Authorization**: Any member in the guild may invoke commands (single-tenant trusted group). No role gate in MVP.
- **Voice requirement**: `entrar` requires author to be in a voice channel

## Commands

### `!cronista entrar`

Inicia gravação no canal de voz do autor.

| Condition | Response |
|-----------|----------|
| Author not in voice channel | "Entre em um canal de voz antes de usar este comando." |
| Session already active | "Já estou gravando uma sessão. Use \`!cronista encerrar\` para finalizar." |
| Success | "Gravação iniciada — sessão \`{session_id}\` no canal **{channel_name}**." |

**Side effects**:
- Bot joins voice channel (deafened, muted)
- Creates `{RECORDINGS_DIR}/{session_id}/session.json`
- Starts audio receiver

---

### `!cronista encerrar`

Finaliza sessão ativa manualmente.

| Condition | Response |
|-----------|----------|
| No active session | "Não há sessão em andamento." |
| Success + webhook OK | "Sessão \`{session_id}\` encerrada. Pipeline de transcrição notificado." |
| Success + webhook failed | "Sessão \`{session_id}\` encerrada, mas a notificação ao n8n falhou (marcado em session.json)." |

**Side effects**:
- Sets `ended_at` in session.json
- Destroys voice connection
- POST webhook to `N8N_WEBHOOK_URL` (if configured)

---

### `!cronista status`

Consulta estado da gravação.

| Condition | Response |
|-----------|----------|
| No active session | "Nenhuma sessão em andamento." |
| Active session | Multi-line: recording status, session_id, duration (Xh Ym Zs), participant count |

---

### `!cronista` / `!cronista help`

Lista comandos disponíveis.

## Auto-End Behavior (not a command)

When voice channel has zero human members for `AUTO_END_EMPTY_CHANNEL_MS` (default 5 min):
- Same side effects as `encerrar`
- No chat response required (optional: log to stdout)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | yes | — | Bot token |
| `RECORDINGS_DIR` | no | `./recordings` | Output directory |
| `UTTERANCE_SILENCE_MS` | no | `1000` | Silence duration to close utterance |
| `AUTO_END_EMPTY_CHANNEL_MS` | no | `300000` | Auto-end when channel empty (5 min) |
| `N8N_WEBHOOK_URL` | no | — | Webhook destination; skip if unset |

See also: [session-json.schema.json](./session-json.schema.json), [speaking-log.schema.json](./speaking-log.schema.json), [n8n-webhook.schema.json](./n8n-webhook.schema.json)
