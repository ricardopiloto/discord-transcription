# Data Model: whisper-service

**Feature**: whisper-service  
**Date**: 2026-07-12

## Overview

Serviço **stateless** — não persiste entidades em disco. O modelo de dados descreve payloads HTTP, configuração de runtime e relação com artefatos do Cronista (somente leitura).

```text
Cronista (upstream)                    whisper-service              n8n (downstream)
─────────────────                    ───────────────              ────────────────
recordings/{session_id}/             POST /transcribe  ────────►  transcript lines
  {user_id}/NNNN.ogg    ──path──►    GET /health                  montagem final
  speaking_log.jsonl                 (stateless)
```

---

## Entity: TranscribeRequest

Corpo JSON de `POST /transcribe`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio_path` | string | yes | Caminho absoluto do arquivo de áudio no host |
| `language` | string | yes | Código ISO 639-1 (ex.: `pt`, `en`) |

### Validation Rules

- `audio_path` MUST ser caminho absoluto
- `audio_path` MUST existir no filesystem → senão HTTP 404
- `audio_path` SHOULD estar sob prefixo permitido (config `WHISPER_ALLOWED_PATH_PREFIX`, default `/opt/apps/cronista/recordings/`) — rejeitar path traversal (`..`)
- Extensões aceitas: `.ogg`, `.wav`, `.mp3`, `.m4a`, `.flac` (faster-whisper/ffmpeg); primário do Cronista é `.ogg`
- `language` MUST ser string não vazia, 2–5 caracteres

### Example

```json
{
  "audio_path": "/opt/apps/cronista/recordings/20260710-220100/123456789/0001.ogg",
  "language": "pt"
}
```

---

## Entity: TranscribeResponse

Resposta HTTP 200 de transcrição bem-sucedida.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | Texto transcrito (pode ser vazio para áudio silencioso) |
| `language` | string | yes | Idioma usado/detectado |
| `duration_s` | number (float ≥ 0) | yes | Duração do áudio processado em segundos |

### Validation Rules

- `text` trimmed; segmentos concatenados com espaço
- `duration_s` derivado do metadata do áudio ou soma de segmentos Whisper

### Example

```json
{
  "text": "Vocês entram na taverna e sentem o cheiro de cerveja derramada.",
  "language": "pt",
  "duration_s": 4.2
}
```

---

## Entity: ErrorResponse

Resposta de erro (404, 500, 422).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `detail` | string | yes | Mensagem legível (padrão FastAPI) |

### Examples

```json
{ "detail": "Arquivo não encontrado: /caminho/informado.ogg" }
```

```json
{ "detail": "Falha na transcrição: invalid opus packet" }
```

---

## Entity: HealthResponse

Resposta de `GET /health` quando serviço pronto.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | yes | `"ok"` quando modelo carregado e pronto |
| `model` | string | yes | Valor efetivo de `WHISPER_MODEL_SIZE` |
| `compute_type` | string | yes | Valor efetivo de `WHISPER_COMPUTE_TYPE` |

### State: Loading (startup)

Durante carregamento do modelo, endpoint MAY retornar HTTP 503 com:

```json
{ "status": "loading", "model": "small", "compute_type": "int8" }
```

Comportamento exato documentado em [contracts/api.md](./contracts/api.md).

---

## Entity: RuntimeConfig

Configuração carregada de variáveis de ambiente na inicialização.

| Field | Env Var | Default | Description |
|-------|---------|---------|-------------|
| `model_size` | `WHISPER_MODEL_SIZE` | `small` | Tamanho do modelo Whisper |
| `compute_type` | `WHISPER_COMPUTE_TYPE` | `int8` | Quantização CTranslate2 |
| `host` | `WHISPER_HOST` | `0.0.0.0` | Bind address |
| `port` | `WHISPER_PORT` | `8008` | Porta HTTP |
| `allowed_path_prefix` | `WHISPER_ALLOWED_PATH_PREFIX` | `/opt/apps/cronista/recordings/` | Prefixo permitido para `audio_path` |

### Validation Rules

- `model_size` ∈ {`tiny`, `base`, `small`, `medium`, `large-v3`, `large-v2`, `large`}
- `compute_type` ∈ {`int8`, `int8_float16`, `int16`, `float16`, `float32`} — MVP usa `int8`
- `port` ∈ [1024, 65535]
- Falha na inicialização (modelo inválido) MUST encerrar processo com log explícito (systemd restart)

---

## Entity: WhisperModelSingleton (in-memory)

Estado interno do processo — não exposto via API.

| State | Description |
|-------|-------------|
| `uninitialized` | Processo subindo; health = loading |
| `ready` | Modelo em RAM; aceita `/transcribe` |
| `transcribing` | Processando uma requisição (serializado no MVP) |

### Lifecycle

```text
[uninitialized] ──load model──► [ready]
[ready] ──POST /transcribe──► [transcribing] ──done──► [ready]
```

MVP: uma transcrição por vez (n8n sequencial); requisições concorrentes SHOULD aguardar ou retornar 503 — implementação escolhe lock simples.

---

## Relationship to Cronista Artifacts

| Cronista artifact | whisper-service usage |
|-------------------|----------------------|
| `{user_id}/NNNN.ogg` | Input via `audio_path` |
| `speaking_log.jsonl` | n8n lê entries; monta path absoluto antes de chamar `/transcribe` |
| `session.json` | Não consumido diretamente pelo whisper-service |

**Contratos Cronista (001/002) permanecem inalterados.**

---

## Entity: n8n Transcript Line (downstream, for reference)

O workflow n8n agrega resultados — não é persistido pelo whisper-service, mas informa o consumo:

| Field | Source |
|-------|--------|
| `user_id` | `speaking_log.jsonl` entry |
| `seq` | `speaking_log.jsonl` entry |
| `text` | `TranscribeResponse.text` |
| `start_ms`, `end_ms` | `speaking_log.jsonl` entry |

Ver [contracts/n8n-integration.md](./contracts/n8n-integration.md).
