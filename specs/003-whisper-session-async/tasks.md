---
description: "Task list for whisper-service session async (v2)"
---

# Tasks: Transcrição assíncrona por sessão (whisper-service v2)

**Input**: Design documents from `/specs/003-whisper-session-async/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unitários e contract HTTP no polish + onde indicado nas stories (plan.md); cenários manuais = [quickstart.md](./quickstart.md). Sem TDD obrigatório.

**Organization**: Por user story (US1–US5). Código em `whisper-service/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência incompleta)
- **[Story]**: US1–US5 conforme spec.md
- Caminhos relativos ao repo root

## Path Conventions

```text
whisper-service/whisper_service/   # implementação
whisper-service/tests/unit/        # unitários
whisper-service/tests/contract/    # TestClient / contratos HTTP
specs/003-whisper-session-async/   # design (já existe)
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirmar base v1 e preparar extensão — sem recriar o serviço.

- [x] T001 Verify package layout exists: `whisper-service/whisper_service/{main,schemas,paths,transcriber,config}.py` and `whisper-service/tests/`
- [x] T002 [P] Ensure `whisper-service/tests/contract/` directory exists (create empty `__init__` or keep as package)
- [x] T003 [P] Bump package version to `0.3.0` in `whisper-service/pyproject.toml` (semver feature)

**Checkpoint**: Repo pronto para módulos de sessão.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schemas, store, formatação e validação de path — **bloqueia todas as user stories**.

**⚠️ CRITICAL**: Nenhuma story começa até esta fase estar completa.

**Constitution**: Schemas em `specs/003-whisper-session-async/contracts/` já existem; implementação Pydantic deve alinhá-los. Sem spike DAVE (N/A).

- [x] T004 [P] Extend path helpers to validate absolute dirs/files under prefix in `whisper-service/whisper_service/paths.py` (reuse resolve + `relative_to`; keep `validate_audio_path`)
- [x] T005 [P] Add Pydantic models for session request/accepted/status/callback payloads in `whisper-service/whisper_service/schemas.py` per `specs/003-whisper-session-async/contracts/`
- [x] T006 [P] Implement `format_timestamp_ms` + `format_transcript_line` + name fallback + silence marker `(silêncio)` in `whisper-service/whisper_service/transcript_format.py`
- [x] T007 Implement thread-safe `SessionStore` (get/start/reject-if-in-progress/update progress/finish done|failed/reprocess) in `whisper-service/whisper_service/session_store.py`
- [x] T008 Create shared `ThreadPoolExecutor(max_workers=1)` lifecycle (module-level or app lifespan) for session jobs in `whisper-service/whisper_service/session_worker.py` (stub submit API OK)
- [x] T009 [P] Implement callback POST via stdlib `urllib` with 3 attempts and backoff 2s/5s/10s in `whisper-service/whisper_service/callback.py`

**Checkpoint**: Foundation ready — user stories can proceed.

---

## Phase 3: User Story 1 - Aceitar sessão e processar em segundo plano (Priority: P1) 🎯 MVP

**Goal**: `POST /transcribe-session` → 202 imediato; lote em thread; escreve `transcricao.txt`; notifica callback em sucesso.

**Independent Test**: Request com `speaking_log` + áudios válidos → 202 &lt; 1s; ao fim existe `transcricao.txt` no formato `[HH:MM:SS] Nome: texto` / `(silêncio)`; callback recebe `status=done`.

**Covers**: FR-001, FR-002, FR-004, FR-005, FR-008 (sucesso), FR-011, FR-013, SC-001, SC-004, SC-005

### Implementation for User Story 1

- [x] T010 [US1] Implement session batch loop in `whisper-service/whisper_service/session_worker.py`: read `speaking_log.jsonl`, resolve `{recordings_path}/{file}`, call `transcriber.transcribe(..., "pt")`, skip missing audio with warning, sort by `start_ms`, write `transcricao.txt` only on full success
- [x] T011 [US1] On fatal error in worker: mark store `failed`, do **not** write `transcricao.txt`, invoke failed callback payload (FR-014) in `whisper-service/whisper_service/session_worker.py`
- [x] T012 [US1] Wire `POST /transcribe-session` in `whisper-service/whisper_service/main.py`: validate paths (403), reject if model loading (503), start store + submit worker, return 202 accepted body
- [x] T013 [US1] After successful write, call `callback.notify` with done payload (`output_path`, totals, `channel_id`) from worker in `whisper-service/whisper_service/session_worker.py`
- [x] T014 [US1] Count `utterances_com_texto` excluding `(silêncio)` lines when finishing done state in `whisper-service/whisper_service/session_worker.py`

**Checkpoint**: MVP — aceite + lote + arquivo + callback básico funcionam.

---

## Phase 4: User Story 2 - Impedir processamento duplicado (Priority: P1)

**Goal**: Segunda solicitação com mesma `session_id` em `in_progress` → 409; após `done`/`failed` permite reprocessar.

**Independent Test**: Com sessão `in_progress`, segundo POST → 409 e um único lote; após `done`, novo POST inicia de novo.

**Covers**: FR-003, SC-002

### Implementation for User Story 2

- [x] T015 [US2] Enforce 409 in `POST /transcribe-session` when `SessionStore` reports `in_progress` for `session_id` in `whisper-service/whisper_service/main.py` (detail message per contracts/api.md)
- [x] T016 [US2] Ensure reprocess replaces prior `done`/`failed` state and starts new job in `whisper-service/whisper_service/session_store.py` + `main.py`
- [x] T017 [P] [US2] Add contract tests for 202 vs 409 in `whisper-service/tests/contract/test_transcribe_session.py` (mock/stub worker if needed)

**Checkpoint**: Lock por sessão cobre o incidente de produção.

---

## Phase 5: User Story 3 - Acompanhar progresso (Priority: P1)

**Goal**: `GET /status/{session_id}` com progresso incremental e estados finais.

**Independent Test**: Durante lote, `processed` cresce; ao fim `done` com `output_path` ou `failed` com `error`; id desconhecido → 404.

**Covers**: FR-006, FR-007, FR-012, SC-003

### Implementation for User Story 3

- [x] T018 [US3] Update `processed`/`total` in store after each utterance (including skipped missing files) in `whisper-service/whisper_service/session_worker.py`
- [x] T019 [US3] Implement `GET /status/{session_id}` returning SessionStatus or 404 in `whisper-service/whisper_service/main.py`
- [x] T020 [P] [US3] Add contract tests for status `in_progress`/`done`/`failed`/404 in `whisper-service/tests/contract/test_session_status.py`

**Checkpoint**: Status consultável sem grepar logs.

---

## Phase 6: User Story 4 - Serviço responsivo durante o lote (Priority: P1)

**Goal**: `/health` e `/status` respondem enquanto o lote CPU roda (não bloqueiam o event loop).

**Independent Test**: Com lote longo em andamento, `/health` e `/status` retornam em tempo normal.

**Covers**: FR-010, SC-006

### Implementation for User Story 4

- [x] T021 [US4] Confirm session work never runs on the asyncio event loop (only via executor thread) in `whisper-service/whisper_service/main.py` + `session_worker.py`
- [x] T022 [US4] Add optional model access lock so `/transcribe` and session worker do not re-enter CTranslate2 unsafely in `whisper-service/whisper_service/transcriber.py` (or thin wrapper used by both)
- [x] T023 [P] [US4] Add unit/contract smoke that `/health` returns 200 while a fake long job holds the executor in `whisper-service/tests/contract/test_health_during_session.py`

**Checkpoint**: Operador não mata o processo achando que travou.

---

## Phase 7: User Story 5 - Notificar conclusão com retry (Priority: P2)

**Goal**: Callback com até 3 tentativas e backoff; falha final só em log; status permanece consultável.

**Independent Test**: Receptor falha 2× depois aceita → 3ª OK; ou 3 falhas → log ERROR e `GET /status` ainda `done`/`failed`.

**Covers**: FR-009, SC-007

### Implementation for User Story 5

- [x] T024 [US5] Harden `callback.py` timeouts (≈10s) and logging of attempt failures in `whisper-service/whisper_service/callback.py`
- [x] T025 [US5] Ensure worker always attempts callback on both `done` and `failed` paths and never clears store on callback failure in `whisper-service/whisper_service/session_worker.py`
- [x] T026 [P] [US5] Unit tests for backoff/retry counting with mocked URL opener in `whisper-service/tests/unit/test_callback.py`

**Checkpoint**: Ciclo n8n resistente a restart momentâneo do webhook.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs, testes de formatação, regressão v1, validação quickstart.

- [x] T027 [P] Unit tests for transcript formatting (silence, name fallback, HH:MM:SS) in `whisper-service/tests/unit/test_transcript_format.py`
- [x] T028 [P] Unit tests for `SessionStore` transitions (409 path via `try_start`, reprocess) in `whisper-service/tests/unit/test_session_store.py`
- [x] T029 [P] Unit tests for path prefix rejection of session dirs in `whisper-service/tests/unit/test_paths.py`
- [x] T030 [P] Update `whisper-service/README.md` with `/transcribe-session`, `/status`, callback notes
- [x] T031 [P] Update `whisper-service/contracts/api.md` (or link) to point to session contracts under `specs/003-whisper-session-async/contracts/`
- [x] T032 [P] Add `0.3.0` entry to root `CHANGELOG.md` summarizing session-async endpoints
- [x] T033 Document n8n cutover notes (replace per-utterance loop) in `whisper-service/contracts/n8n-integration.md` or short section in README
- [x] T034 Run unit + contract pytest suite under `whisper-service/`
- [x] T035 Execute applicable scenarios from `specs/003-whisper-session-async/quickstart.md` and tick checklist
- [x] T036 Verify v1 `POST /transcribe` + `GET /health` still pass existing tests / Scenario 8

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: imediato
- **Foundational (Phase 2)**: após Setup — **bloqueia** US1–US5
- **US1 (Phase 3)**: após Foundational — MVP
- **US2 (Phase 4)**: após US1 (reusa POST + store)
- **US3 (Phase 5)**: após Foundational; progresso real exige worker US1 (T018)
- **US4 (Phase 6)**: após US1 (executor já usado)
- **US5 (Phase 7)**: após US1 callback path (T013/T011)
- **Polish (Phase 8)**: após stories desejadas

### User Story Dependencies

```text
Phase 2 Foundational
        │
        ▼
       US1 (MVP: 202 + lote + arquivo + callback)
      / | \
     /  |  \
   US2 US3 US4
            \
            US5 (retry endurecido)
```

- **US1**: sem dependência de outras stories
- **US2**: depende do endpoint US1
- **US3**: store na foundation; updates no worker US1
- **US4**: confirma offload já introduzido em US1
- **US5**: refina callback criado na foundation/US1

### Parallel Opportunities

- Phase 1: T002, T003 em paralelo após T001
- Phase 2: T004, T005, T006, T009 em paralelo; T007/T008 após ou em paralelo cuidadoso
- Phase 8: T027–T032 em paralelo
- US2 contract (T017) // US3 contract (T020) após endpoints prontos

### Parallel Example: Foundational

```bash
# Em paralelo (arquivos distintos):
Task: T004 paths.py
Task: T005 schemas.py
Task: T006 transcript_format.py
Task: T009 callback.py
# Depois:
Task: T007 session_store.py
Task: T008 session_worker.py stub + executor
```

### Parallel Example: Polish

```bash
Task: T027 test_transcript_format.py
Task: T028 test_session_store.py
Task: T029 test_paths.py
Task: T030 README.md
Task: T032 CHANGELOG.md
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2
2. Phase 3 (US1)
3. **STOP**: validar Scenario 1 + 4 do quickstart
4. Seguir US2 → US3 → US4 → US5 → Polish

### Incremental Delivery

1. Setup + Foundational
2. US1 → demo aceite + `transcricao.txt`
3. US2 → proteção 409
4. US3 → observabilidade `/status`
5. US4 → confiança operacional `/health`
6. US5 → resiliência callback
7. Polish → 0.3.0 + docs + pytest + quickstart

### Suggested MVP scope

**US1 apenas** (T001–T014): já desbloqueia o corte do loop n8n por utterance. US2 é fortemente recomendado antes de produção (mesmo P1).

---

## Notes

- Idioma do lote fixo `pt`; sem campo `language` no request
- `(silêncio)` não conta em `utterances_com_texto`
- Áudio ausente: continua lote, sem linha
- Erro fatal: `failed`, sem arquivo, callback failed
- Não alterar contratos Cronista (`speaking_log.jsonl`)
- Commit por task ou grupo lógico; validar checkpoint de cada story
