# API Contract: whisper-service

**Feature**: whisper-service  
**Base URL (host)**: `http://host.docker.internal:8008` (n8n em Docker)  
**Base URL (local dev)**: `http://localhost:8008`

Schemas JSON: [transcribe-request.schema.json](./transcribe-request.schema.json), [transcribe-response.schema.json](./transcribe-response.schema.json), [health-response.schema.json](./health-response.schema.json)

---

## POST /transcribe

Transcreve um arquivo de áudio identificado por caminho absoluto no host.

### Request

**Headers**: `Content-Type: application/json`

**Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio_path` | string | yes | Caminho absoluto do arquivo (ex.: `.ogg` do Cronista) |
| `language` | string | yes | Código ISO 639-1 (ex.: `pt`) |

**Example**:

```json
{
  "audio_path": "/opt/apps/cronista/recordings/20260710-220100/123456789/0001.ogg",
  "language": "pt"
}
```

### Responses

| Status | Body | Condition |
|--------|------|-----------|
| 200 | [TranscribeResponse](./transcribe-response.schema.json) | Transcrição concluída |
| 404 | `{ "detail": "Arquivo não encontrado: …" }` | `audio_path` não existe |
| 403 | `{ "detail": "Caminho não permitido: …" }` | Path fora do prefixo configurado |
| 422 | `{ "detail": … }` | Body inválido (campo ausente, etc.) |
| 500 | `{ "detail": "…" }` | Falha na transcrição (arquivo corrompido, formato inválido) |
| 503 | `{ "detail": "Modelo ainda carregando" }` | Startup em andamento |

**Success example**:

```json
{
  "text": "Vocês entram na taverna e sentem o cheiro de cerveja derramada.",
  "language": "pt",
  "duration_s": 4.2
}
```

---

## GET /health

Verifica disponibilidade e configuração do modelo carregado.

### Responses

| Status | Body | Condition |
|--------|------|-----------|
| 200 | [HealthResponse](./health-response.schema.json) | Modelo carregado, serviço pronto |
| 503 | `{ "status": "loading", "model": "…", "compute_type": "…" }` | Modelo ainda carregando |

**Ready example**:

```json
{
  "status": "ok",
  "model": "small",
  "compute_type": "int8"
}
```

---

## Operational Notes

- **Timeout recomendado (cliente n8n)**: 120s por utterance
- **Concorrência**: MVP assume chamadas sequenciais; serviço roda com worker único
- **Autenticação**: nenhuma — isolamento por firewall na porta 8008
- **Content-Type**: sempre `application/json`

Ver também: [n8n-integration.md](./n8n-integration.md)
