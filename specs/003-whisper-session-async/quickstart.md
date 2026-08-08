# Quickstart: Transcrição assíncrona por sessão

**Feature**: `003-whisper-session-async`  
**Contracts**: [contracts/api.md](./contracts/api.md) · **Data model**: [data-model.md](./data-model.md)

Validação manual pós-implementação (não substitui pytest de contrato/unit).

## Prerequisites

- whisper-service instalado/rodando (venv + systemd ou `uvicorn` local)
- `WHISPER_ALLOWED_PATH_PREFIX` apontando para o diretório de gravações de teste
- Sessão Cronista de teste com `speaking_log.jsonl` + `.ogg` (pode ser fixture mínima com ≥3 utterances)
- Porta do serviço acessível (`localhost:8008` ou host de produção)

## Setup

```bash
cd whisper-service
# ativar venv de deploy ou local
export WHISPER_ALLOWED_PATH_PREFIX=/caminho/para/recordings/
# garantir modelo carregado
curl -sS http://127.0.0.1:8008/health
```

Esperado: `"status":"ok"`.

## Scenario 1 — Aceite imediato (SC-001)

```bash
SESSION_DIR=/caminho/para/recordings/SESSION_ID
curl -sS -o /tmp/ts-accept.json -w "%{http_code} time=%{time_total}\n" \
  -X POST http://127.0.0.1:8008/transcribe-session \
  -H 'Content-Type: application/json' \
  -d "{
    \"session_id\": \"SESSION_ID\",
    \"recordings_path\": \"${SESSION_DIR}\",
    \"speaking_log_path\": \"${SESSION_DIR}/speaking_log.jsonl\",
    \"participants\": [{\"user_id\": \"111\", \"display_name\": \"Alice\"}],
    \"channel_id\": \"ch-test\",
    \"callback_url\": \"http://127.0.0.1:9999/webhook-dummy\"
  }"
cat /tmp/ts-accept.json
```

**Esperado**: HTTP **202**, body `status=accepted`, `time_total` &lt; 1s.

## Scenario 2 — Conflito 409 (SC-002)

Com o lote do Scenario 1 ainda `in_progress`, repetir o mesmo `POST` com a mesma `session_id`.

**Esperado**: HTTP **409**; um único lote continua (status `processed` monotônico).

## Scenario 3 — Status incremental (SC-003)

Durante um lote com ≥100 utterances (ou fixture grande):

```bash
for i in 1 2 3; do
  curl -sS "http://127.0.0.1:8008/status/SESSION_ID"
  sleep 5
done
```

**Esperado**: três leituras com `status=in_progress` e `processed` estritamente crescente; ao fim `done` + `output_path`.

## Scenario 4 — Arquivo e formato (SC-004)

```bash
head -n 5 "${SESSION_DIR}/transcricao.txt"
```

**Esperado**: linhas `[HH:MM:SS] Nome: …`; silêncios como `(silêncio)`; ordenação cronológica.

## Scenario 5 — Health durante o lote (SC-006)

Com lote em andamento:

```bash
curl -sS -w " time=%{time_total}\n" http://127.0.0.1:8008/health
```

**Esperado**: HTTP 200 `ok` em tempo normal (não hang de minutos).

## Scenario 6 — Path rejeitado (FR-013)

`POST` com `recordings_path` fora do prefixo permitido.

**Esperado**: HTTP **403**; nenhum estado criado (`GET /status/...` → 404).

## Scenario 7 — Callback / fallback status (SC-005, SC-007)

1. Apontar `callback_url` para um receptor que registra o body (n8n webhook de teste ou `nc`/servidor mínimo).
2. Completar um lote curto → payload `status=done` com totais coerentes.
3. (Opcional) Receptor que falha nas 2 primeiras respostas → 3ª tentativa ou conferência via `GET /status`.

## Scenario 8 — Regressão v1

```bash
curl -sS -X POST http://127.0.0.1:8008/transcribe \
  -H 'Content-Type: application/json' \
  -d "{\"audio_path\":\"${SESSION_DIR}/USER/0001.ogg\",\"language\":\"pt\"}"
```

**Esperado**: HTTP 200 com `text` / `duration_s` (contrato v1 intacto).

## Checklist

- [x] Scenario 1 — 202 &lt; 1s (coberto por contract test + mock worker inline)
- [x] Scenario 2 — 409 (contract test)
- [x] Scenario 3 — `processed` crescente (store + status contract; lote longo = manual em prod)
- [x] Scenario 4 — `transcricao.txt` formato OK (unit format + contract write)
- [x] Scenario 5 — `/health` durante lote (smoke contract; validar com modelo real em prod)
- [x] Scenario 6 — 403 path (contract test)
- [x] Scenario 7 — callback retry (unit test_callback; webhook real = manual)
- [x] Scenario 8 — `/transcribe` v1 (suite existente)
