# Implementation Plan: Transcrição assíncrona por sessão (whisper-service v2)

**Branch**: `003-whisper-session-async` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-whisper-session-async/spec.md` (+ `docs/demanda-whisper-service-v2.md`)

## Summary

Estender o **whisper-service** existente para processar uma sessão Cronista inteira em background: `POST /transcribe-session` (202 + lock 409), loop local sobre `speaking_log.jsonl` + `model.transcribe()`, escrita de `transcricao.txt` no formato legado, callback HTTP com retry, e `GET /status/{session_id}` com progresso incremental. Endpoints v1 `/transcribe` e `/health` permanecem. Status em memória; processamento CPU em thread dedicada para não bloquear o event loop.

## Technical Context

**Language/Version**: Python 3.11–3.13 (mesmo runtime do whisper-service)

**Primary Dependencies**: FastAPI, uvicorn (workers=1), faster-whisper, python-dotenv; HTTP client de callback via stdlib (`urllib`) ou `httpx` promovido a dep de runtime (ver research)

**Storage**: Lê artefatos Cronista no filesystem; escreve `transcricao.txt` ao final do lote; status de sessão **somente em memória**

**Testing**: pytest (unit + contract HTTP com TestClient/httpx); validação E2E manual via [quickstart.md](./quickstart.md)

**Target Platform**: Linux host compartilhado, systemd, `/opt/apps/whisper-service/` (mesmo deploy da v1)

**Project Type**: Extensão incremental de microserviço HTTP existente (`whisper-service/`)

**Performance Goals**: Aceite `<1s`; `/health` e `/status` responsivos durante lote; progresso `processed` estritamente crescente em lotes ≥100

**Constraints**:
- Idioma do lote fixo `pt`
- Paths sob `WHISPER_ALLOWED_PATH_PREFIX`
- Uma thread de lote (serial por utterance); workers uvicorn = 1
- Sem persistência de status; escrita de transcript só em sucesso
- Manter contrato v1 `/transcribe` / `/health`

**Scale/Scope**: 1 processo; sessões ~664–2.000 utterances; duas sessões distintas podem coexistir e disputar CPU

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Principle | Gate Question | Status | Notes |
|-----------|---------------|--------|-------|
| I. Contract Stability | Contratos downstream preservados? | ✅ PASS | Cronista `speaking_log` / paths intactos; `transcricao.txt` formato legado; v1 HTTP preservada; **novo** contrato sessão/callback documentado em `contracts/` e coordenado com n8n |
| II. Evidence Before Commitment | Riscos empíricos com spike? | ✅ N/A → gate manual | Sem risco DAVE; validação empírica = quickstart (aceite &lt;1s, 409, status incremental, health durante lote, callback) |
| III. Simplicity & YAGNI | Single-process, file-based, escopo delimitado? | ✅ PASS | Sem DB/fila; dict em memória; ThreadPoolExecutor 1 worker; sem UI |
| IV. Incremental Durability | Gravação incremental? | ✅ N/A | Princípio aplica-se ao bot; aqui transcript só ao final (spec/out of scope) |
| V. Operational Isolation | Isolamento + convivência? | ✅ PASS | Mesmo venv/systemd whisper-service; `WHISPER_CPU_THREADS` permanece |

**Post-design re-check**: Design não adiciona persistência, workers extras nem auth. Complexity Tracking vazio. Gates mantidos.

## Project Structure

### Documentation (this feature)

```text
specs/003-whisper-session-async/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── api.md
│   ├── transcribe-session-request.schema.json
│   ├── transcribe-session-accepted.schema.json
│   ├── session-status.schema.json
│   └── session-callback.schema.json
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks (não criado aqui)
```

### Source Code (repository root)

```text
whisper-service/
├── whisper_service/
│   ├── main.py              # + rotas /transcribe-session, /status/{id}
│   ├── schemas.py           # + Pydantic request/status/callback
│   ├── paths.py             # reusar / estender validação de prefixo p/ dirs
│   ├── transcriber.py       # reusar transcribe() síncrono
│   ├── session_store.py     # NOVO: estado em memória + lock por session_id
│   ├── session_worker.py    # NOVO: loop do lote + formatação + escrita
│   ├── transcript_format.py # NOVO: HH:MM:SS + (silêncio) + fallback nome
│   └── callback.py          # NOVO: POST callback + 3 retries backoff
├── tests/
│   ├── unit/                # store, format, path, worker helpers
│   └── contract/            # 202/409/status/callback mock
├── contracts/               # v1 (permanece); contratos v2 vivem em specs/003…
├── .env.example
└── README.md
```

**Structure Decision**: Extender o pacote `whisper-service/whisper_service/` existente. Artefatos de design desta feature ficam em `specs/003-whisper-session-async/` (padrão monorepo Spec Kit). Contratos v1 em `whisper-service/contracts/` permanecem a fonte de verdade do `/transcribe` e `/health`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 → Research

Ver [research.md](./research.md) — decisões: background thread, lock in-memory, backoff callback, formatação, path validation, http client.

## Phase 1 → Design

| Artifact | Path | Status |
|----------|------|--------|
| Data model | [data-model.md](./data-model.md) | ✅ |
| API contract | [contracts/api.md](./contracts/api.md) | ✅ |
| JSON Schemas | [contracts/](./contracts/) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |

## Next Steps

1. `/speckit-tasks` — decompor implementação
2. `/speckit-implement` — código + testes
3. Atualizar workflow n8n para `/transcribe-session` + webhook de conclusão
4. Bump versão whisper-service (ex.: 0.3.0) + CHANGELOG
