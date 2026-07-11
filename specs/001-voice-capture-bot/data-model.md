# Data Model: Bot de Captura de Voz

**Feature**: 001-voice-capture-bot  
**Date**: 2026-07-10

## Overview

Modelo file-based sem banco de dados. Três artefatos persistidos por sessão + áudio binário por utterance.

```text
{RECORDINGS_DIR}/
  {session_id}/
    session.json           # Metadados da sessão (atualizado incrementalmente)
    speaking_log.jsonl     # Append-only, um JSON por utterance
    {discord_user_id}/
      0001.ogg
      0002.ogg
      ...
```

---

## Entity: Session

Representa uma partida de RPG gravada.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | `YYYYMMDD-HHmmss`, unique per deployment |
| `guild_id` | string | yes | Discord guild snowflake |
| `channel_id` | string | yes | Discord voice channel snowflake |
| `started_at` | string (ISO 8601 UTC) | yes | Session start timestamp |
| `ended_at` | string (ISO 8601 UTC) | no | Set on session end |
| `participants` | Participant[] | yes | May start empty, grows as users speak |
| `webhook_failed` | boolean | no | `true` if n8n notification failed after retries |

### State Transitions

```text
[none] ──start()──► [recording]
[recording] ──end()──► [ended]
[recording] ──crash──► [orphaned]  (out of scope: no auto-recovery)
```

### Validation Rules

- `session_id` MUST match regex `^\d{8}-\d{6}$`
- Only one `[recording]` session per `guild_id` at a time (FR-018)
- `ended_at` MUST be ≥ `started_at` when present
- `webhook_failed` only meaningful when `ended_at` is set

### In-Memory Singleton

`SessionManager` holds at most one active session globally (single-bot deployment). Guard rejects second `start()` while recording.

---

## Entity: Participant

Jogador ou GM registrado por falar durante a sessão.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | yes | Discord user snowflake |
| `display_name` | string | yes | Guild display name at first utterance |
| `utterance_count` | integer ≥ 0 | yes | Incremented on each closed utterance |

### Relationships

- Belongs to **Session** (embedded in `session.json` participants array)
- Has many **Utterance** (via files + speaking log entries)

### Validation Rules

- `user_id` unique within session participants list
- `utterance_count` incremented atomically on utterance close
- Participant added on first detected speech, not on channel join alone

---

## Entity: Utterance (Segmento de fala)

Unidade mínima de áudio — turno contínuo de fala de um participante.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | yes | Owner participant |
| `seq` | integer ≥ 1 | yes | Sequential per user within session |
| `file` | string | yes | Relative path: `{user_id}/{NNNN}.ogg` |
| `start_ms` | integer ≥ 0 | yes | Ms from `session.started_at` |
| `end_ms` | integer ≥ 0 | yes | Ms from `session.started_at` |
| `duration_ms` | integer ≥ 0 | yes | `end_ms - start_ms` |

### File Naming

- Pattern: `{user_id}/{seq zero-padded to 4 digits}.ogg`
- Example: `123456789/0042.ogg`

### Validation Rules

- `seq` unique per `(session_id, user_id)`
- `end_ms` ≥ `start_ms`
- `duration_ms` = `end_ms - start_ms`
- File MUST exist on disk when speaking log entry is written

### Persistence

- **Binary**: Ogg Opus file on disk
- **Metadata**: one line in `speaking_log.jsonl`

---

## Entity: SpeakingLog

Append-only log for chronological reconstruction across participants.

| Property | Value |
|----------|-------|
| Format | JSON Lines (one JSON object per line) |
| File | `{session_dir}/speaking_log.jsonl` |
| Ordering | Insertion order ≈ chronological (sorted by `start_ms` for merge) |

Each line conforms to **Utterance** metadata fields (see schema in `contracts/speaking-log.schema.json`).

---

## Entity: WebhookNotification

Payload POST único ao encerrar sessão. Not a persisted entity — derived from Session at end time.

See `contracts/n8n-webhook.schema.json`.

---

## Runtime State (in-memory only)

| State | Owner | Description |
|-------|-------|-------------|
| `activeSession` | SessionManager | Current SessionData or null |
| `sessionDir` | SessionManager | Absolute path to session folder |
| `startedAtMs` | SessionManager | Epoch ms for relative timestamps |
| `voiceConnection` | SessionManager | Active @discordjs/voice connection |
| `utteranceCounters` | AudioRecorder | Map userId → last seq |
| `emptyChannelTimer` | Bot client | Timeout handle for auto-end |

---

## TypeScript Mapping

Existing interfaces in `src/types/session.ts`:

| Entity | TypeScript |
|--------|------------|
| Session | `SessionData` |
| Participant | `Participant` |
| Utterance (log entry) | `SpeakingLogEntry` |
| WebhookNotification | `WebhookPayload` |

No changes required to type definitions — they match this model.
