# Data Model: Transcrição assíncrona por sessão

**Feature**: `003-whisper-session-async`  
**Date**: 2026-08-08  
**Spec**: [spec.md](./spec.md)

## Overview

O serviço deixa de ser puramente stateless: mantém **estado de sessão em memória** durante/após o lote. Artefatos Cronista continuam a fonte de áudio/metadados; a saída nova é `transcricao.txt` + callback ao n8n.

```text
n8n                          whisper-service                         disco
───                          ───────────────                         ─────
POST /transcribe-session ──► SessionStore (in_progress)
                             SessionWorker (thread)
                               ├─ read speaking_log.jsonl ─────────► recordings/...
                               ├─ transcribe each .ogg
                               ├─ write transcricao.txt ───────────► recordings/.../transcricao.txt
                               └─ POST callback_url ───────────────► n8n webhook
GET /status/{id} ◄────────── SessionStore
```

---

## Entity: SessionTranscribeRequest

Corpo de `POST /transcribe-session`. Schema: [contracts/transcribe-session-request.schema.json](./contracts/transcribe-session-request.schema.json)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Id da sessão Cronista (ex. `20260807-231300`) |
| `recordings_path` | string | yes | Diretório absoluto da sessão |
| `speaking_log_path` | string | yes | Path absoluto do `speaking_log.jsonl` |
| `participants` | Participant[] | yes | Mapa id→nome (pode ser `[]`) |
| `channel_id` | string | yes | Canal Discord (ecoado no callback) |
| `callback_url` | string | yes | URL HTTP(S) para notificação de término |

### Participant

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | yes | Snowflake Discord |
| `display_name` | string | yes | Nome de exibição; se vazio, runtime usa `user_id` |
| `utterance_count` | integer | no | Informativo; não governa o loop |

### Validation Rules

- `session_id` não vazio
- `recordings_path` e `speaking_log_path` absolutos, sob `WHISPER_ALLOWED_PATH_PREFIX`, sem `..` → senão **403**
- `callback_url` MUST ser URL http/https absoluta
- Idioma implícito: sempre `pt` (sem campo)

---

## Entity: SessionAcceptedResponse

Resposta **202**. Schema: [contracts/transcribe-session-accepted.schema.json](./contracts/transcribe-session-accepted.schema.json)

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"accepted"` | Constante |
| `session_id` | string | Eco do request |

---

## Entity: SessionState (in-memory)

Estado consultável via `GET /status/{session_id}`. Schema: [contracts/session-status.schema.json](./contracts/session-status.schema.json)

| Field | Type | When | Description |
|-------|------|------|-------------|
| `status` | enum | always | `in_progress` \| `done` \| `failed` |
| `processed` | int ≥ 0 | always | Utterances já consideradas no loop |
| `total` | int ≥ 0 | always | Linhas no speaking_log (0 se falhou antes de ler) |
| `started_at` | string (ISO-8601 UTC) | always | Início do lote |
| `finished_at` | string \| omit | `done`/`failed` | Fim do lote |
| `utterances_com_texto` | int ≥ 0 \| omit | `done` | Linhas com texto real (exclui `(silêncio)`) |
| `output_path` | string \| omit | `done` | Path absoluto de `transcricao.txt` |
| `error` | string \| omit | `failed` | Mensagem de erro |

### State Transitions

```text
(absent) --accept--> in_progress --success--> done
                   \               \--fatal--> failed
                    \
                     (se já in_progress) --> HTTP 409, sem transição

done|failed --new accept--> in_progress  (reprocess; substitui estado)
```

### Concurrency

- Mutações do store sob lock.
- Apenas um lote `in_progress` por `session_id`.
- Sessões **diferentes** podem estar `in_progress` simultaneamente (disputam CPU).

---

## Entity: SessionCallbackPayload

POST JSON ao `callback_url`. Schema: [contracts/session-callback.schema.json](./contracts/session-callback.schema.json)

### Success (`status: "done"`)

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | |
| `status` | `"done"` | |
| `output_path` | string | Path de `transcricao.txt` |
| `total_utterances` | int | = `total` |
| `utterances_com_texto` | int | |
| `channel_id` | string | |

### Failure (`status: "failed"`)

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | |
| `status` | `"failed"` | |
| `error` | string | |
| `total_utterances` | int | opcional mas recomendado |
| `channel_id` | string | |

---

## Entity: TranscriptLine (arquivo)

Não é JSON API — linhas de texto em `{recordings_path}/transcricao.txt`.

| Aspect | Rule |
|--------|------|
| Formato | `[HH:MM:SS] Nome: texto` |
| Ordem | `start_ms` ascendente |
| Silêncio | `texto` = `(silêncio)` |
| Nome | `display_name` ou fallback `user_id` |
| Encoding | UTF-8 |
| Escrita | Somente ao concluir com sucesso; overwrite se existir |

---

## Entity: SpeakingLogEntry (upstream, read-only)

Contrato Cronista (inalterado): ver `specs/001-voice-capture-bot/contracts/speaking-log.schema.json`.

Campos usados pelo worker: `user_id`, `file`, `start_ms`.

---

## Runtime Config (herdado)

Sem novas env vars obrigatórias nesta fase. Continuam: `WHISPER_MODEL`, `WHISPER_COMPUTE_TYPE`, `WHISPER_CPU_THREADS`, `WHISPER_ALLOWED_PATH_PREFIX`, host/port.

| Constant (código) | Value | Description |
|-------------------|-------|-------------|
| Callback max attempts | 3 | |
| Callback backoff | 2s, 5s, 10s | Entre tentativas |
| Session language | `pt` | Fixo |

---

## Relationships

- **SessionTranscribeRequest** 1 → cria/atualiza **SessionState**
- **SessionState** 1 → 0..1 arquivo **TranscriptLine[]** (`output_path` só em `done`)
- **SessionState** 1 → 1 tentativa de **SessionCallbackPayload** (com retries)
- **Participant[]** resolve nomes para **TranscriptLine**
