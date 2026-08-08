# API Contract: whisper-service v2 (session async)

**Feature**: `003-whisper-session-async`  
**Base URL (host)**: `http://host.docker.internal:8008` (n8n em Docker)  
**Base URL (local)**: `http://localhost:8008`

**v1 preserved**: [whisper-service/contracts/api.md](../../../whisper-service/contracts/api.md) — `POST /transcribe`, `GET /health` inalterados.

Schemas desta feature:
- [transcribe-session-request.schema.json](./transcribe-session-request.schema.json)
- [transcribe-session-accepted.schema.json](./transcribe-session-accepted.schema.json)
- [session-status.schema.json](./session-status.schema.json)
- [session-callback.schema.json](./session-callback.schema.json)

---

## POST /transcribe-session

Aceita lote de sessão; processa em background.

### Request

**Headers**: `Content-Type: application/json`  
**Body**: [SessionTranscribeRequest](./transcribe-session-request.schema.json)

```json
{
  "session_id": "20260807-231300",
  "recordings_path": "/opt/apps/cronista/recordings/20260807-231300",
  "speaking_log_path": "/opt/apps/cronista/recordings/20260807-231300/speaking_log.jsonl",
  "participants": [
    { "user_id": "693962506573578270", "display_name": "Ricardo", "utterance_count": 42 }
  ],
  "channel_id": "id_do_canal_discord",
  "callback_url": "http://127.0.0.1:5678/webhook/cronista-transcricao-concluida"
}
```

### Responses

| Status | Body | Condition |
|--------|------|-----------|
| 202 | [Accepted](./transcribe-session-accepted.schema.json) | Aceito; lote iniciado |
| 409 | `{ "detail": "Sessão … já está sendo processada" }` | Mesma `session_id` com `in_progress` |
| 403 | `{ "detail": "Caminho não permitido: …" }` | Path fora de `WHISPER_ALLOWED_PATH_PREFIX` |
| 422 | `{ "detail": … }` | Body inválido |
| 503 | `{ "detail": "Modelo ainda carregando" }` | Startup |

**Notas**:
- Idioma do lote: sempre `pt` (sem campo).
- Reprocessar após `done`/`failed` com a mesma `session_id` é permitido (substitui estado).

---

## GET /status/{session_id}

### Responses

| Status | Body | Condition |
|--------|------|-----------|
| 200 | [SessionStatus](./session-status.schema.json) | Sessão conhecida em memória |
| 404 | `{ "detail": "Sessão desconhecida: …" }` | Nunca iniciada ou perdida após restart |

### Exemplos

`in_progress`:

```json
{
  "status": "in_progress",
  "processed": 340,
  "total": 664,
  "started_at": "2026-08-08T02:52:00Z"
}
```

`done`:

```json
{
  "status": "done",
  "processed": 664,
  "total": 664,
  "utterances_com_texto": 610,
  "output_path": "/opt/apps/cronista/recordings/20260807-231300/transcricao.txt",
  "started_at": "2026-08-08T02:52:00Z",
  "finished_at": "2026-08-08T04:15:00Z"
}
```

`failed`:

```json
{
  "status": "failed",
  "error": "mensagem do erro",
  "processed": 210,
  "total": 664,
  "started_at": "2026-08-08T02:52:00Z",
  "finished_at": "2026-08-08T03:01:00Z"
}
```

---

## Callback (outbound)

`POST` para `callback_url` após término. Schema: [session-callback.schema.json](./session-callback.schema.json)

- Retries: 3 tentativas; backoff 2s, 5s, 10s
- Sucesso cliente: HTTP 2xx
- Timeout sugerido no cliente do serviço: 10s

Success:

```json
{
  "session_id": "20260807-231300",
  "status": "done",
  "output_path": "/opt/apps/cronista/recordings/20260807-231300/transcricao.txt",
  "total_utterances": 664,
  "utterances_com_texto": 610,
  "channel_id": "id_do_canal_discord"
}
```

Failure:

```json
{
  "session_id": "20260807-231300",
  "status": "failed",
  "error": "mensagem do erro",
  "total_utterances": 664,
  "channel_id": "id_do_canal_discord"
}
```

---

## Operational Notes

- Autenticação: nenhuma (firewall na porta 8008)
- CPU: `WHISPER_CPU_THREADS` (default 5)
- Arquivo de saída: `{recordings_path}/transcricao.txt`, formato `[HH:MM:SS] Nome: texto` / `(silêncio)`
- Conteúdo: sempre `application/json`
